from urllib.parse import urlencode
from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login as django_login
from apps.accounts.models import User
from apps.applications.models import Application
from common.response import success, error
from common.errors import ErrorCode
from common.utils import create_access_token, generate_refresh_token
from .models import AuthCode
from .utils import validate_redirect_uri, generate_auth_code, verify_app_secret


def authorize(request):
    app_id = request.GET.get("app_id")
    redirect_uri = request.GET.get("redirect_uri")
    state = request.GET.get("state", "")
    response_type = request.GET.get("response_type", "")

    if response_type != "code":
        return HttpResponseBadRequest("不支持的 response_type")

    try:
        app = Application.objects.get(id=app_id, status=True)
    except Application.DoesNotExist:
        return HttpResponseBadRequest("应用不存在或已禁用")

    if not validate_redirect_uri(app, redirect_uri):
        return HttpResponseBadRequest("回调地址不在白名单中")

    request.session["oauth_app_id"] = app_id
    request.session["oauth_redirect_uri"] = redirect_uri
    request.session["oauth_state"] = state

    if not request.user.is_authenticated:
        login_url = reverse("oauth_login_page")
        params = urlencode({
            "next": reverse("oauth_authorize") + f"?app_id={app_id}&redirect_uri={redirect_uri}&response_type=code"
        })
        return redirect(f"{login_url}?{params}")

    # 已登录但不属于应用所属租户：回到登录页换账号，避免跨租户授权
    if request.user.tenant_id != app.tenant_id:
        return render(request, "oauth2/login.html", {
            "error": "当前账号不属于该应用所属租户，请使用本租户账号登录",
            "next": request.get_full_path(),
        })

    return render(request, "oauth2/confirm.html", {
        "app": app,
        "user": request.user,
        "redirect_uri": redirect_uri,
        "state": state,
    })


def authorize_confirm(request):
    if request.method != "POST":
        return redirect("oauth_authorize")
    if not request.user.is_authenticated:
        return redirect("oauth_login_page")

    app_id = request.session.get("oauth_app_id")
    redirect_uri = request.session.get("oauth_redirect_uri")
    state = request.session.get("oauth_state", "")

    try:
        app = Application.objects.get(id=app_id, status=True)
    except Application.DoesNotExist:
        return HttpResponseBadRequest("应用不存在或已禁用")

    # 兜底：授权确认阶段再次校验账号与应用租户一致
    if request.user.tenant_id != app.tenant_id:
        return HttpResponseForbidden("当前账号不属于该应用所属租户")

    auth_code = generate_auth_code(app, request.user, redirect_uri, state)

    params = {"code": auth_code.code}
    if state:
        params["state"] = state
    separator = "&" if "?" in redirect_uri else "?"
    callback_url = f"{redirect_uri}{separator}{urlencode(params)}"

    return redirect(callback_url)


def authorize_deny(request):
    redirect_uri = request.session.get("oauth_redirect_uri", "")
    state = request.session.get("oauth_state", "")
    params = {"error": "access_denied"}
    if state:
        params["state"] = state
    separator = "&" if "?" in redirect_uri else "?"
    callback_url = f"{redirect_uri}{separator}{urlencode(params)}"
    return redirect(callback_url)


def oauth_login_page(request):
    if request.method == "POST":
        next_url = request.GET.get("next") or request.POST.get("next") or reverse("oauth_authorize")

        # 第二步：用户名在多个租户命中，已由用户选定租户（候选用户保存在会话中，无需再次提交密码）
        if request.POST.get("select_tenant"):
            tenant_id = (request.POST.get("tenant_id") or "").strip()
            candidate_ids = request.session.pop("oauth_login_candidate_ids", [])
            user = User.objects.filter(id__in=candidate_ids, tenant_id=tenant_id, status=1).first()
            if user is None:
                return render(request, "oauth2/login.html", {
                    "error": "租户选择已失效，请重新输入用户名和密码",
                    "next": next_url,
                })
            django_login(request, user)
            return redirect(next_url)

        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        if not username or not password:
            return render(request, "oauth2/login.html", {
                "error": "请输入用户名和密码",
                "next": next_url,
            })

        # OAuth2 登录始终绑定发起授权的应用所属租户，同名用户不再产生歧义
        app = Application.objects.filter(id=request.session.get("oauth_app_id"), status=True).first()
        users = User.objects.select_related("tenant").filter(username=username)
        if app is not None:
            users = users.filter(tenant_id=app.tenant_id)
        matched = [u for u in users if u.status == 1 and u.check_password(password)]
        if len(matched) == 1:
            django_login(request, matched[0])
            return redirect(next_url)
        if len(matched) > 1:
            request.session["oauth_login_candidate_ids"] = [u.id for u in matched]
            return render(request, "oauth2/login.html", {
                "tenants": [
                    {"tenant_id": u.tenant_id, "tenant_name": u.tenant.name} for u in matched
                ],
                "next": next_url,
            })
        return render(request, "oauth2/login.html", {
            "error": "用户名或密码错误",
            "next": next_url,
        })
    return render(request, "oauth2/login.html", {
        "next": request.GET.get("next", ""),
    })


@csrf_exempt
def token_exchange(request):
    if request.method != "POST":
        return JsonResponse(error(ErrorCode.PARAM_INVALID, message="仅支持 POST"), status=405)

    grant_type = request.POST.get("grant_type", "")
    code = request.POST.get("code", "")
    app_id = request.POST.get("app_id", "")
    app_secret = request.POST.get("app_secret", "")
    redirect_uri = request.POST.get("redirect_uri", "")

    if grant_type != "authorization_code":
        return JsonResponse(error(ErrorCode.PARAM_INVALID, message="不支持的 grant_type"), status=400)

    try:
        app = Application.objects.get(id=app_id, status=True)
    except Application.DoesNotExist:
        return JsonResponse(error(ErrorCode.APP_KEY_INVALID), status=401)

    if not verify_app_secret(app, app_secret):
        return JsonResponse(error(ErrorCode.SIGNATURE_INVALID), status=401)

    # 防御：授权码用户与应用必须同租户，杜绝跨租户换取 Token
    try:
        auth_code = AuthCode.objects.select_related("user").get(code=code, app=app)
    except AuthCode.DoesNotExist:
        return JsonResponse(error(ErrorCode.TOKEN_INVALID, message="授权码无效"), status=400)

    if auth_code.user.tenant_id != app.tenant_id:
        return JsonResponse(error(ErrorCode.PERMISSION_DENIED, message="授权用户不属于应用所属租户"), status=403)

    if auth_code.is_used:
        return JsonResponse(error(ErrorCode.TOKEN_INVALID, message="授权码已被使用"), status=400)

    if auth_code.is_expired:
        return JsonResponse(error(ErrorCode.TOKEN_EXPIRED, message="授权码已过期"), status=400)

    if auth_code.redirect_uri != redirect_uri:
        return JsonResponse(error(ErrorCode.PARAM_INVALID, message="redirect_uri 不匹配"), status=400)

    auth_code.mark_used()

    user = auth_code.user
    access_token = create_access_token({
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "user_type": user.user_type,
        "app_id": app.id,
    })
    refresh_token = generate_refresh_token({
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "user_type": user.user_type,
        # 保留应用上下文，刷新后的 access_token 仍需受应用准入约束
        "app_id": app.id,
    })

    return JsonResponse(success({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "user_type": user.user_type,
        "expires_in": 7200,
    }))