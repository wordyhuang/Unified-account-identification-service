from urllib.parse import urlencode
from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login as django_login
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
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None and user.status == 1:
            django_login(request, user)
            next_url = request.GET.get("next", reverse("oauth_authorize"))
            return redirect(next_url)
        return render(request, "oauth2/login.html", {
            "error": "用户名或密码错误",
            "next": request.GET.get("next", ""),
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

    try:
        auth_code = AuthCode.objects.get(code=code, app=app)
    except AuthCode.DoesNotExist:
        return JsonResponse(error(ErrorCode.TOKEN_INVALID, message="授权码无效"), status=400)

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
    refresh_token = generate_refresh_token()

    return JsonResponse(success({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": user.id,
        "tenant_id": user.tenant_id,
        "user_type": user.user_type,
        "expires_in": 7200,
    }))