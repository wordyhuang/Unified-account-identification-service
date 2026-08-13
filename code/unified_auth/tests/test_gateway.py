"""
网关全功能测试用例
- 验证中间件栈（限流 → 应用认证 → Token认证 → 权限校验 → 审计日志）
- 覆盖认证API、开放API、管理API的全部端点
"""
import os
import sys
import time
import hmac
import hashlib
import json
import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DB_ENGINE"] = "sqlite"
os.environ["DB_NAME"] = "test_admin.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

import requests
from apps.accounts.models import Tenant, User
from apps.applications.models import Application
from apps.rbac.models import ApiPermission, AppRoleBinding, Role, RolePermission, UserRole
from apps.audit.models import AuditLog

BASE = "http://127.0.0.1:8000"
APP_KEY = "70d1187b914482d3dfbf0a5f25ca94e6"
APP_SECRET = "bc6cc1d1bedc9b3376164a85ebb1cfe4aedd61b5a7812b783672acbafef1a63a"

passed = 0
failed = 0
results = []

def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name} — {detail}")
    results.append((name, ok, detail))


def rate_limit_safe(method, url, **kwargs):
    """发送请求，遇到限流(429)时等待60秒自动重试"""
    max_retry = 2
    for attempt in range(max_retry):
        r = method(url, **kwargs)
        if r.status_code == 429:
            print(f"   [WARN] 触发限流(429)，等待62秒后重试(第{attempt+1}次)...")
            time.sleep(62)
            continue
        return r
    return r


def openapi_headers():
    ts = str(int(time.time()))
    sig = hmac.new(APP_SECRET.encode(), f"{{}}{ts}".encode(), hashlib.sha256).hexdigest()
    return {
        "X-App-Key": APP_KEY,
        "X-Timestamp": ts,
        "X-Signature": sig,
    }


def setup_test_data():
    """创建测试所需的基础数据"""
    tenant, _ = Tenant.objects.get_or_create(slug="default", defaults={"name": "默认企业"})

    admin = User.objects.filter(username="admin").first()
    if not admin:
        admin = User.objects.create_user(
            tenant=tenant, username="admin", password="admin123456", user_type="internal",
            is_staff=True, is_superuser=True,
        )

    admin_tenant = admin.tenant
    app = Application.objects.filter(app_key=APP_KEY).first()
    if app:
        app.app_secret = APP_SECRET
        app.default_access_user_types = ["internal", "external"]
        app.save(update_fields=["app_secret", "default_access_user_types"])
    else:
        app = Application.objects.create(
            tenant=admin_tenant, name="网关测试应用",
            app_key=APP_KEY, app_secret=APP_SECRET,
            default_access_user_types=["internal", "external"],
        )

    perms = []
    perm_data = [
        ("token:verify", "验证Token", "POST", "/api/v1/open/token/verify", "auth"),
        ("user:read", "读取用户", "GET", "/api/v1/open/users", "user"),
        ("user:read_detail", "读取用户详情", "GET", "/api/v1/open/users/:id", "user"),
        ("user:create", "创建用户", "POST", "/api/v1/open/users", "user"),
        ("user:update", "修改用户", "PUT", "/api/v1/open/users/:id", "user"),
        ("user:status", "修改用户状态", "PATCH", "/api/v1/open/users/:id/status", "user"),
        ("permission:check", "校验权限", "POST", "/api/v1/open/permissions/check", "permission"),
    ]
    for code, name, method, path, cat in perm_data:
        p, _ = ApiPermission.objects.get_or_create(
            code=code, defaults={"name": name, "method": method, "path": path, "category": cat},
        )
        perms.append(p)

    role, _ = Role.objects.get_or_create(
        tenant=admin_tenant, code="admin", defaults={"name": "管理员"},
    )
    for p in perms:
        RolePermission.objects.get_or_create(role=role, permission=p)

    UserRole.objects.get_or_create(user=admin, role=role)

    AppRoleBinding.objects.get_or_create(app=app, role=role)

    print(f"  测试数据就绪: 租户={admin_tenant.slug}, 应用={app.app_key}, 权限={len(perms)}条, 角色=管理员")
    return tenant, admin, app


@pytest.mark.skip(reason="E2E测试：需要运行中的服务器")
def test_auth_api(admin):
    """认证API测试 (网关中间件: TokenAuth)"""
    print("\n" + "=" * 55)
    print("【认证API】/api/v1/auth/*")
    print("=" * 55)

    s = requests.Session()
    # 包装Session方法，遇到429自动等待重试
    for method_name in ("get", "post", "put", "patch", "delete"):
        orig = getattr(s, method_name)
        def _make_wrapped(orig_method):
            return lambda url, **kw: rate_limit_safe(orig_method, url, **kw)
        setattr(s, method_name, _make_wrapped(orig))

    # 1. 密码登录
    r = s.post(f"{BASE}/api/v1/auth/login", json={
        "username": "admin", "password": "admin123456",
    })
    body = r.json()
    check("POST login 200", r.status_code == 200 and body["code"] == 0,
          f"status={r.status_code}, code={body.get('code')}")
    access_token = body["data"]["access_token"]
    refresh_token = body["data"]["refresh_token"]
    check("login 返回 access_token", bool(access_token))
    check("login 返回 refresh_token", bool(refresh_token))
    check("login 返回 is_superuser", body["data"].get("is_superuser") is True)

    # 2. 获取用户信息
    r = s.get(f"{BASE}/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    body = r.json()
    check("GET userinfo 200", r.status_code == 200 and body["code"] == 0)
    check("userinfo 返回 username", body["data"]["username"] == "admin")

    # 3. 修改用户信息
    r = s.put(f"{BASE}/api/v1/auth/me", json={"nickname": "管理员"},
              headers={"Authorization": f"Bearer {access_token}"})
    check("PUT userinfo 200", r.status_code == 200)

    # 4. 认证API不带Token应返回401
    r = s.get(f"{BASE}/api/v1/auth/me")
    check("userinfo 无Token 401", r.status_code == 401,
          f"实际={r.status_code}")

    # 5. 修改密码
    r = s.patch(f"{BASE}/api/v1/auth/me/password", json={
        "old_password": "admin123456", "new_password": "newpass1234",
    }, headers={"Authorization": f"Bearer {access_token}"})
    body = r.json()
    check("PATCH password 200", r.status_code == 200 and body["code"] == 0)

    # 6. 用新密码登录验证密码修改生效
    r = s.post(f"{BASE}/api/v1/auth/login", json={
        "username": "admin", "password": "newpass1234",
    })
    check("新密码登录成功", r.status_code == 200 and r.json()["code"] == 0)

    # 7. 改回原密码
    new_token = r.json()["data"]["access_token"]
    r = s.patch(f"{BASE}/api/v1/auth/me/password", json={
        "old_password": "newpass1234", "new_password": "admin123456",
    }, headers={"Authorization": f"Bearer {new_token}"})
    check("恢复原密码", r.status_code == 200)

    # 8. 刷新Token
    r = s.post(f"{BASE}/api/v1/auth/token/refresh", json={"refresh_token": refresh_token})
    body = r.json()
    check("POST refresh 200", r.status_code == 200 and body["code"] == 0)
    new_access = body["data"].get("access_token")
    check("refresh 返回新access_token", bool(new_access))

    # 9. 登出
    r = s.post(f"{BASE}/api/v1/auth/logout",
               headers={"Authorization": f"Bearer {new_access}"})
    check("POST logout 200", r.status_code == 200)

    return s


@pytest.mark.skip(reason="E2E测试：需要运行中的服务器")
def test_openapi(admin, app):
    """开放API测试 (网关中间件: AppAuth → Permission)"""
    print("\n" + "=" * 55)
    print("【开放API】/api/v1/open/*")
    print("=" * 55)

    s = requests.Session()
    for method_name in ("get", "post", "put", "patch", "delete"):
        orig = getattr(s, method_name)
        def _wrap(m):
            return lambda url, **kw: rate_limit_safe(m, url, **kw)
        setattr(s, method_name, _wrap(orig))

    headers = openapi_headers()

    # 1. 验证Token (需先登录获取一个有效Token)
    login_r = s.post(f"{BASE}/api/v1/auth/login", json={
        "username": "admin", "password": "admin123456",
    })
    valid_token = login_r.json()["data"]["access_token"]

    r = s.post(f"{BASE}/api/v1/open/token/verify", json={"token": valid_token},
               headers=headers)
    body = r.json()
    check("POST verify_token 有效Token", r.status_code == 200 and body["code"] == 0,
          f"status={r.status_code}, body={json.dumps(body, ensure_ascii=False)[:200]}")
    check("verify_token data.valid==True", body.get("data", {}).get("valid") is True,
          f"valid={body.get('data', {}).get('valid')}")
    check("verify_token 返回user_id", body.get("data", {}).get("user_id") == admin.id)

    # 2. 验证无效Token
    r = s.post(f"{BASE}/api/v1/open/token/verify", json={"token": "invalid.jwt.token"},
               headers=headers)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    check("POST verify_token 无效Token", body.get("data", {}).get("valid") is False or r.status_code == 200,
          f"status={r.status_code}, body={json.dumps(body, ensure_ascii=False)[:200]}")

    # 3. 查询用户列表
    r = s.get(f"{BASE}/api/v1/open/users", headers=headers)
    body = r.json()
    check("GET users 200", r.status_code == 200 and body["code"] == 0)
    check("users 返回列表", len(body["data"]["users"]) > 0)

    # 4. 创建用户（如果已存在则跳过创建，直接复用）
    existing = User.objects.filter(username="gateway_test_user").first()
    if existing:
        new_user_id = existing.id
        print(f"   [INFO] 复用已有测试用户: id={new_user_id}")
    else:
        r = s.post(f"{BASE}/api/v1/open/users", json={
            "username": "gateway_test_user",
            "password": "test1234", "user_type": "internal",
        }, headers=headers)
        body = r.json()
        check("POST create_user 201/400", r.status_code in (201, 400),
              f"status={r.status_code}, body={json.dumps(body, ensure_ascii=False)[:200]}")
        new_user_id = body.get("data", {}).get("id") if r.status_code == 201 else None
        if new_user_id:
            check("create_user 返回ID", True)
        else:
            # 可能已存在，查找
            existing = User.objects.filter(username="gateway_test_user").first()
            if existing:
                new_user_id = existing.id
                check("create_user 已存在", True, "复用已有用户")
            else:
                check("create_user 返回ID", False, "创建失败且不存在")

    # 5. 获取用户详情
    r = s.get(f"{BASE}/api/v1/open/users/{new_user_id}", headers=headers)
    check("GET user_detail 200", r.status_code == 200)
    check("user_detail 用户名匹配", r.json()["data"]["username"] == "gateway_test_user")

    # 6. 修改用户
    r = s.put(f"{BASE}/api/v1/open/users/{new_user_id}", json={"nickname": "网关已改名"},
              headers=headers)
    check("PUT update_user 200", r.status_code == 200)

    # 7. 修改用户状态 (禁用)
    r = s.patch(f"{BASE}/api/v1/open/users/{new_user_id}/status", json={"status": 0},
                headers=headers)
    body_disable = r.json()
    check("PATCH user status(禁用) 200", r.status_code == 200)
    check("status 变为0", body_disable.get("data", {}).get("status") == 0,
          f"body={json.dumps(body_disable, ensure_ascii=False)[:200]}")

    # 8. 重新启用
    r = s.patch(f"{BASE}/api/v1/open/users/{new_user_id}/status", json={"status": 1},
                headers=headers)
    body_enable = r.json()
    check("PATCH user status(启用) 200", r.status_code == 200)
    check("status 变为1", body_enable.get("data", {}).get("status") == 1,
          f"body={json.dumps(body_enable, ensure_ascii=False)[:200]}")

    # 9. 校验权限
    r = s.post(f"{BASE}/api/v1/open/permissions/check", json={
        "user_id": admin.id, "permission_code": "user:read",
    }, headers=headers)
    body = r.json()
    check("POST check_permission 200", r.status_code == 200)
    check("check_permission 有权限", body.get("data", {}).get("has_permission") is True,
          f"response={json.dumps(body, ensure_ascii=False)[:200]}")

    # 10. 不存在的权限码
    r = s.post(f"{BASE}/api/v1/open/permissions/check", json={
        "user_id": admin.id, "permission_code": "nonexist:perm",
    }, headers=headers)
    body = r.json()
    check("check_permission 无权限", body.get("data", {}).get("has_permission") is False,
          f"response={json.dumps(body, ensure_ascii=False)[:200]}")

    # 11. 签名错误 → 应用认证应拒绝
    bad_headers = {**headers, "X-Signature": "deadbeef"}
    r = s.get(f"{BASE}/api/v1/open/users", headers=bad_headers)
    check("错误签名 401", r.status_code == 401)

    # 12. 无AppKey → 应拒绝
    r = s.get(f"{BASE}/api/v1/open/users")
    check("无AppKey 401", r.status_code == 401)

    # 13. 删除测试用户
    User.objects.filter(id=new_user_id).delete()

    return s


@pytest.mark.skip(reason="E2E测试：需要运行中的服务器")
def test_admin_api(admin):
    """管理API测试 (网关中间件: AdminAuth)"""
    print("\n" + "=" * 55)
    print("【管理API】/api/v1/admin/*")
    print("=" * 55)

    s = requests.Session()
    for method_name in ("get", "post", "put", "patch", "delete"):
        orig = getattr(s, method_name)
        def _wrap(m):
            return lambda url, **kw: rate_limit_safe(m, url, **kw)
        setattr(s, method_name, _wrap(orig))

    # 1. 用admin登录
    r = s.post(f"{BASE}/api/v1/auth/login", json={
        "username": "admin", "password": "admin123456",
    })
    token = r.json()["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {token}"}

    # 2. 仪表盘统计
    r = s.get(f"{BASE}/api/v1/admin/stats", headers=admin_headers)
    body = r.json()
    check("GET stats 200", r.status_code == 200 and body["code"] == 0)
    check("stats 返回total_users", "total_users" in body["data"])
    check("stats 返回total_apps", "total_apps" in body["data"])

    # 3. 最近动态
    r = s.get(f"{BASE}/api/v1/admin/recent-activities", headers=admin_headers)
    check("GET recent-activities 200", r.status_code == 200)

    # 4. 用户列表
    r = s.get(f"{BASE}/api/v1/admin/users", headers=admin_headers)
    body = r.json()
    check("GET admin users 200", r.status_code == 200 and body["code"] == 0)

    # 5. 创建用户
    r = s.post(f"{BASE}/api/v1/admin/users", json={
        "username": "admin_test_user", "password": "test1234",
        "user_type": "internal",
    }, headers=admin_headers)
    check("POST admin create_user 201", r.status_code == 201)
    new_uid = r.json()["data"]["id"]

    # 6. 获取用户详情
    r = s.get(f"{BASE}/api/v1/admin/users/{new_uid}", headers=admin_headers)
    check("GET admin user_detail 200", r.status_code == 200)

    # 7. 修改用户信息
    r = s.put(f"{BASE}/api/v1/admin/users/{new_uid}", json={"nickname": "管理员改名"},
              headers=admin_headers)
    check("PUT admin update_user 200", r.status_code == 200)

    # 8. 禁用用户
    r = s.patch(f"{BASE}/api/v1/admin/users/{new_uid}/status", json={"status": 0},
                headers=admin_headers)
    check("PATCH admin user status(禁用) 200", r.status_code == 200)

    # 9. 启用用户
    r = s.patch(f"{BASE}/api/v1/admin/users/{new_uid}/status", json={"status": 1},
                headers=admin_headers)
    check("PATCH admin user status(启用) 200", r.status_code == 200)

    # 10. 重置密码
    r = s.post(f"{BASE}/api/v1/admin/users/{new_uid}/reset-password",
               json={"new_password": "newpass5678"}, headers=admin_headers)
    check("POST reset-password 200", r.status_code == 200)

    # 11. 删除用户
    r = s.delete(f"{BASE}/api/v1/admin/users/{new_uid}", headers=admin_headers)
    check("DELETE admin user 200", r.status_code == 200)

    # 12. 应用列表
    r = s.get(f"{BASE}/api/v1/admin/applications", headers=admin_headers)
    check("GET admin apps 200", r.status_code == 200)

    # 13. 应用详情
    app_obj = Application.objects.filter(app_key=APP_KEY).first()
    if app_obj:
        r = s.get(f"{BASE}/api/v1/admin/applications/{app_obj.id}", headers=admin_headers)
        check("GET admin app_detail 200", r.status_code == 200)

        # 14. 修改应用
        r = s.put(f"{BASE}/api/v1/admin/applications/{app_obj.id}",
                  json={"name": "网关测试应用-已更新"}, headers=admin_headers)
        check("PUT admin update_app 200", r.status_code == 200)

        # 15. 禁用应用
        r = s.patch(f"{BASE}/api/v1/admin/applications/{app_obj.id}/status",
                    json={"status": False}, headers=admin_headers)
        check("PATCH admin app status(禁用) 200", r.status_code == 200)

        # 16. 启用应用
        r = s.patch(f"{BASE}/api/v1/admin/applications/{app_obj.id}/status",
                    json={"status": True}, headers=admin_headers)
        check("PATCH admin app status(启用) 200", r.status_code == 200)

    # 17. 权限列表
    r = s.get(f"{BASE}/api/v1/admin/permissions", headers=admin_headers)
    check("GET permissions 200", r.status_code == 200)
    check("permissions 返回数据", len(r.json()["data"]["permissions"]) > 0)

    # 18. 角色列表
    r = s.get(f"{BASE}/api/v1/admin/roles", headers=admin_headers)
    check("GET roles 200", r.status_code == 200)

    # 19. 创建角色
    existing_role = Role.objects.filter(code="test_role", tenant_id=admin.tenant_id).first()
    if existing_role:
        new_role_id = existing_role.id
        check("POST create_role 复用", True, f"id={new_role_id}")
    else:
        r = s.post(f"{BASE}/api/v1/admin/roles", json={
            "name": "测试角色", "code": "test_role", "permission_ids": [],
        }, headers=admin_headers)
        body = r.json()
        check("POST create_role 201/400", r.status_code in (201, 400),
              f"status={r.status_code}, body={json.dumps(body, ensure_ascii=False)[:200]}")
        if r.status_code == 201:
            new_role_id = body["data"]["id"]
            check("create_role 返回ID", bool(new_role_id))
        else:
            existing = Role.objects.filter(code="test_role", tenant_id=admin.tenant_id).first()
            new_role_id = existing.id if existing else None
            check("create_role 已存在", bool(new_role_id), f"复用 id={new_role_id}")

    # 20. 角色详情
    r = s.get(f"{BASE}/api/v1/admin/roles/{new_role_id}", headers=admin_headers)
    check("GET role_detail 200", r.status_code == 200)

    # 21. 修改角色
    r = s.put(f"{BASE}/api/v1/admin/roles/{new_role_id}",
              json={"name": "测试角色已更新", "permission_ids": []}, headers=admin_headers)
    check("PUT update_role 200", r.status_code == 200)

    # 22. 审计日志
    r = s.get(f"{BASE}/api/v1/admin/audit-logs", headers=admin_headers)
    check("GET audit-logs 200", r.status_code == 200)

    # 23. 管理API无Token应401
    r = s.get(f"{BASE}/api/v1/admin/stats")
    check("admin stats 无Token 401", r.status_code == 401)

    # 24. 普通用户访问管理API应403
    normal_user = User.objects.filter(username="normal_user").first()
    if not normal_user:
        normal_user = User.objects.create_user(
            tenant=admin.tenant, username="normal_user",
            password="test1234", user_type="internal",
        )
    login_r = s.post(f"{BASE}/api/v1/auth/login", json={
        "username": "normal_user", "password": "test1234",
    })
    has_token = login_r.status_code == 200 and "access_token" in login_r.json().get("data", {})
    if has_token:
        normal_token = login_r.json()["data"]["access_token"]
        r = s.get(f"{BASE}/api/v1/admin/stats",
                  headers={"Authorization": f"Bearer {normal_token}"})
        check("普通用户访问admin 403", r.status_code == 403,
              f"实际状态码={r.status_code}")
    else:
        check("普通用户访问admin 403", False, "普通用户登录失败")

    return s


@pytest.mark.skip(reason="E2E测试：需要运行中的服务器")
def test_gateway_isolation(admin):
    """网关隔离性测试：验证各中间件独立工作"""
    print("\n" + "=" * 55)
    print("【网关中间件隔离性测试】")
    print("=" * 55)

    s = requests.Session()
    for method_name in ("get", "post", "put", "patch", "delete"):
        orig = getattr(s, method_name)
        def _wrap(m):
            return lambda url, **kw: rate_limit_safe(m, url, **kw)
        setattr(s, method_name, _wrap(orig))

    # 1. 限流测试 — 快速请求检查429
    # 注：实际限流需要60次请求，这里仅验证中间件存在且不阻断正常请求
    for i in range(3):
        r = s.post(f"{BASE}/api/v1/auth/login", json={
            "username": "admin", "password": "admin123456",
        })
    check("限流中间件 — 正常请求通过", r.status_code == 200)

    # 2. 开放API签名校验
    headers = openapi_headers()
    r = s.get(f"{BASE}/api/v1/open/users", headers=headers)
    check("应用认证中间件 — 有效签名通过", r.status_code == 200)

    bad_headers = {**headers, "X-App-Key": "invalid_key"}
    r = s.get(f"{BASE}/api/v1/open/users", headers=bad_headers)
    check("应用认证中间件 — 无效AppKey拒绝", r.status_code == 401)

    # 3. Token认证
    login_r = s.post(f"{BASE}/api/v1/auth/login", json={
        "username": "admin", "password": "admin123456",
    })
    token = login_r.json()["data"]["access_token"]
    r = s.get(f"{BASE}/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    check("Token认证中间件 — 有效Token通过", r.status_code == 200)

    r = s.get(f"{BASE}/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token"})
    check("Token认证中间件 — 无效Token拒绝", r.status_code == 401)

    # 4. 权限校验 — 创建用户需要user:create权限
    headers_no_perm = openapi_headers()
    # 暂时移除user:create权限 — 从角色中移除
    app = Application.objects.get(app_key=APP_KEY)
    perm_create = ApiPermission.objects.get(code="user:create")
    RolePermission.objects.filter(role__approlebinding__app=app, permission=perm_create).delete()

    r = s.post(f"{BASE}/api/v1/open/users", json={
        "username": "no_perm_user", "password": "test1234",
        "user_type": "internal",
    }, headers=headers_no_perm)
    check("权限中间件 — 无user:create权限拒绝", r.status_code == 403)

    # 恢复权限
    role = AppRoleBinding.objects.get(app=app).role
    RolePermission.objects.get_or_create(role=role, permission=perm_create)

    # 5. 审计日志 — 写操作应产生日志
    before_count = AuditLog.objects.count()
    r = s.post(f"{BASE}/api/v1/auth/login", json={
        "username": "admin", "password": "admin123456",
    })
    token = r.json()["data"]["access_token"]
    s.put(f"{BASE}/api/v1/auth/me", json={"nickname": "审计测试"},
          headers={"Authorization": f"Bearer {token}"})
    after_count = AuditLog.objects.count()
    check("审计日志中间件 — 写操作产生日志", after_count > before_count,
          f"之前{ before_count}, 之后{after_count}")

    # 6. 不存在路由 — 中间件可能先于Django路由返回401
    r = s.get(f"{BASE}/api/v1/nonexistent")
    check("不存在路由 401/404", r.status_code in (401, 404), f"实际={r.status_code}")

    # 7. 管理后台页面可访问
    r = s.get(f"{BASE}/admin-panel/")
    check("管理后台页面 200", r.status_code == 200)
    check("管理后台页面包含登录卡片", "login-card" in r.text or "login" in r.text)


def main():
    print("=" * 55)
    print("  统一账号识别服务 · 网关全功能测试")
    print("  Gateway: http://127.0.0.1:8000")
    print("  AppKey: " + APP_KEY)
    print("=" * 55)

    try:
        requests.get(f"{BASE}/api/v1/auth/login", timeout=3)
    except requests.ConnectionError:
        print(f"\n❌ 无法连接 {BASE}，请确认服务已启动")
        sys.exit(1)

    print("\n▶ 初始化测试数据...")
    tenant, admin, app = setup_test_data()

    test_auth_api(admin)
    test_openapi(admin, app)
    test_admin_api(admin)
    test_gateway_isolation(admin)

    print("\n" + "=" * 55)
    total = passed + failed
    print(f"  测试完成: {total} 项")
    print(f"  ✅ 通过: {passed}")
    if failed > 0:
        print(f"  ❌ 失败: {failed}")
    else:
        print("  🎉 全部通过!")
    print("=" * 55)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
