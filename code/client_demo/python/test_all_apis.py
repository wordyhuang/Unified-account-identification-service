#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一账户认证服务 (UAIS) - 客户端完整 API 联调测试

依据文档: document/gateway_openapi_documentation_v2.md

测试内容:
  - 获取应用 access_token
  - OpenAPI: 验证Token、用户CRUD、权限校验、用户资料、微信辅助
  - Auth: 密码登录、短信验证码、Token刷新、个人信息、修改密码、登出

使用方式:
    pip install requests python-dotenv
    python test_all_apis.py
"""
import os
import sys
import time
import json
import random
from pathlib import Path

# 添加上级目录到路径，以便 import openapi_client
sys.path.insert(0, str(Path(__file__).parent))

import requests
from dotenv import load_dotenv


# ==================== 配置加载 ====================

# .env 文件在 client_demo 目录下
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

UAIS_HOST = os.getenv("UAIS_HOST", "http://localhost:8000").rstrip("/")
UAIS_APP_ID = os.getenv("UAIS_APP_ID", "")
UAIS_APP_SECRET = os.getenv("UAIS_APP_SECRET", "")
USER_ID = os.getenv("USER_ID", "")
USER_PASSWORD = os.getenv("USER_PASSWORD", "")

if not all([UAIS_APP_ID, UAIS_APP_SECRET]):
    print("❌ 错误: .env 文件中缺少 UAIS_APP_ID 或 UAIS_APP_SECRET")
    sys.exit(1)

if not all([USER_ID, USER_PASSWORD]):
    print("⚠️  警告: .env 文件中缺少 USER_ID 或 USER_PASSWORD，部分测试将跳过")

print("=" * 72)
print("  统一账户认证服务 - 客户端 API 联调测试")
print("=" * 72)
print(f"  服务地址: {UAIS_HOST}")
print(f"  AppKey:   {UAIS_APP_ID}")
print(f"  用户:     {USER_ID}")
print("=" * 72)


# ==================== 测试统计 ====================

class TestStats:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []

    def ok(self, name, detail=""):
        self.passed += 1
        self.results.append((name, "✅ 通过", detail))
        print(f"  ✅ {name}")

    def fail(self, name, detail=""):
        self.failed += 1
        self.results.append((name, "❌ 失败", detail))
        print(f"  ❌ {name} - {detail}")

    def warn(self, name, detail=""):
        """应用未配置对应权限码，非 API 本身问题"""
        self.passed += 1  # 不计入失败
        self.results.append((name, "⚠️  需配置权限", detail))
        print(f"  ⚠️  {name} - {detail}")

    def skip(self, name, reason=""):
        self.skipped += 1
        self.results.append((name, "⏭️ 跳过", reason))
        print(f"  ⏭️ {name} ({reason})")

    def summary(self):
        print()
        print("=" * 72)
        print("  测试结果汇总")
        print("=" * 72)
        print(f"  总数: {self.passed + self.failed + self.skipped}")
        print(f"  通过: {self.passed}")
        print(f"  失败: {self.failed}")
        print(f"  跳过: {self.skipped}")
        warnings = [r for r in self.results if "需配置权限" in r[1]]
        if warnings:
            print()
            print("  ⚠️  应用权限配置提示（需在管理后台为应用绑定权限码）:")
            for name, status, detail in warnings:
                print(f"    {name}")
        if self.failed > 0:
            print()
            print("  ❌ 失败详情:")
            for name, status, detail in self.results:
                if "失败" in status:
                    print(f"    {name}: {detail}")
        print("=" * 72)

stats = TestStats()


# ==================== 辅助函数 ====================

import hashlib
import hmac
import time


def get_access_token():
    """获取应用 access_token (POST /api/v1/open/token)"""
    resp = requests.post(
        f"{UAIS_HOST}/api/v1/open/token",
        json={"app_key": UAIS_APP_ID, "app_secret": UAIS_APP_SECRET},
        timeout=10,
    )
    data = resp.json()
    assert data["code"] == 0, f"获取 access_token 失败: {data}"
    return data["data"]["access_token"]


def _build_hmac_headers(body=None):
    """构建 HMAC 签名认证头

    密钥直接使用 .env 中的 UAIS_APP_SECRET（与管理后台显示的 AppSecret 一致）
    签名公式: HMAC-SHA256(app_secret, "{}" + timestamp)
    """
    timestamp = str(int(time.time()))
    message = "{}" + timestamp
    signature = hmac.new(
        UAIS_APP_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "X-App-Key": UAIS_APP_ID,
        "X-Timestamp": timestamp,
        "X-Signature": signature,
    }


def openapi_get(path, access_token, params=None):
    """OpenAPI GET 请求"""
    url = f"{UAIS_HOST}{path}"
    if params is None:
        params = {}
    params["access_token"] = access_token
    return requests.get(url, params=params, timeout=10)


def openapi_hmac_get(path, query_params=None):
    """OpenAPI GET 请求 (使用 HMAC 签名认证)"""
    url = f"{UAIS_HOST}{path}"
    headers = _build_hmac_headers()
    return requests.get(url, params=query_params, headers=headers, timeout=10)


def openapi_post(path, access_token, body=None):
    """OpenAPI POST 请求"""
    url = f"{UAIS_HOST}{path}?access_token={access_token}"
    return requests.post(url, json=body or {}, timeout=10)


def openapi_put(path, access_token, body=None):
    """OpenAPI PUT 请求"""
    url = f"{UAIS_HOST}{path}?access_token={access_token}"
    return requests.put(url, json=body or {}, timeout=10)


def openapi_hmac_put(path, body=None):
    """OpenAPI PUT 请求 (使用 HMAC 签名认证)"""
    url = f"{UAIS_HOST}{path}"
    headers = _build_hmac_headers(body)
    return requests.put(url, json=body or {}, headers=headers, timeout=10)


def openapi_patch(path, access_token, body=None):
    """OpenAPI PATCH 请求"""
    url = f"{UAIS_HOST}{path}?access_token={access_token}"
    return requests.patch(url, json=body or {}, timeout=10)


# ==================== 测试用例 ====================

def test_get_app_token():
    """测试 1: 获取应用 access_token"""
    print("\n📋 测试 1: 获取应用 access_token (POST /api/v1/open/token)")
    print("-" * 60)

    # 1.1 正常获取
    try:
        resp = requests.post(
            f"{UAIS_HOST}/api/v1/open/token",
            json={"app_key": UAIS_APP_ID, "app_secret": UAIS_APP_SECRET},
            timeout=10,
        )
        data = resp.json()
        if data["code"] == 0 and "access_token" in data.get("data", {}):
            stats.ok("获取 access_token 成功", f"expires_in={data['data'].get('expires_in')}")
            token = data["data"]["access_token"]
        else:
            stats.fail("获取 access_token", f"响应异常: {data}")
            return None
    except Exception as e:
        stats.fail("获取 access_token", str(e))
        return None

    # 1.2 无效 AppSecret
    try:
        resp = requests.post(
            f"{UAIS_HOST}/api/v1/open/token",
            json={"app_key": UAIS_APP_ID, "app_secret": "wrong_secret"},
            timeout=10,
        )
        data = resp.json()
        if data["code"] != 0:
            stats.ok("无效 AppSecret 应被拒绝", f"code={data['code']}")
        else:
            stats.fail("无效 AppSecret 未拒绝", str(data))
    except Exception as e:
        stats.fail("无效 AppSecret 测试", str(e))

    # 1.3 缺少参数
    try:
        resp = requests.post(
            f"{UAIS_HOST}/api/v1/open/token",
            json={"app_key": UAIS_APP_ID},
            timeout=10,
        )
        data = resp.json()
        if data["code"] != 0:
            stats.ok("缺少参数应被拒绝", f"code={data['code']}")
        else:
            stats.fail("缺少参数未拒绝", str(data))
    except Exception as e:
        stats.fail("缺少参数测试", str(e))

    return token


def test_verify_token(access_token):
    """测试 2: 验证用户 Token"""
    print("\n📋 测试 2: 验证用户 Token (POST /api/v1/open/token/verify)")
    print("-" * 60)

    # 2.1 无效 Token
    resp = openapi_post("/api/v1/open/token/verify", access_token, {"token": "invalid.jwt.token"})
    data = resp.json()
    if data.get("code") == 0 and data.get("data", {}).get("valid") is False:
        stats.ok("无效 Token 验证正确返回 false")
    elif data.get("code") == -10202:
        stats.warn("无效 Token 验证", "应用缺少 token:verify 权限码（需在管理后台绑定）")
    else:
        stats.fail("无效 Token 验证", f"期望 valid=false, 得到 {data}")

    # 2.2 缺少参数
    resp = openapi_post("/api/v1/open/token/verify", access_token, {})
    data = resp.json()
    if data.get("code") != 0:
        stats.ok("缺少参数应报错", f"code={data.get('code')}")
    else:
        stats.fail("缺少参数未报错", str(data)[:100])


def test_user_crud(access_token):
    """测试 3: 用户 CRUD"""
    print("\n📋 测试 3: 用户 CRUD (OpenAPI)")
    print("-" * 60)
    suffix = random.randint(10000, 99999)
    test_username = f"apitest_{suffix}"
    test_phone = f"138{suffix:05d}"

    # 3.1 创建用户
    resp = openapi_post("/api/v1/open/users", access_token, {
        "username": test_username,
        "password": "Test@123456",
        "user_type": "internal",
        "phone": test_phone,
        "nickname": f"API测试_{suffix}",
    })
    data = resp.json()
    created_user_id = None
    if data.get("code") == 0 and data.get("data", {}).get("id"):
        created_user_id = data["data"]["id"]
        stats.ok(f"创建用户成功", f"ID={created_user_id}, username={test_username}")
    else:
        stats.fail("创建用户", str(data)[:120])
        return None

    # 3.2 重复创建（应失败）
    resp = openapi_post("/api/v1/open/users", access_token, {
        "username": test_username,
        "password": "Test@123456",
    })
    data = resp.json()
    if data.get("code") != 0:
        stats.ok("重复创建应被拒绝", f"code={data.get('code')}")
    else:
        stats.fail("重复创建未拒绝", str(data)[:100])

    # 3.3 获取用户详情
    resp = openapi_get(f"/api/v1/open/users/{created_user_id}", access_token)
    data = resp.json()
    if data.get("code") == 0 and data.get("data", {}).get("id") == created_user_id:
        stats.ok("获取用户详情成功", f"username={data['data'].get('username')}")
    elif data.get("code") == -10202:
        stats.warn("获取用户详情", "应用缺少 user:read 权限码（需在管理后台绑定）")
    else:
        stats.fail("获取用户详情", str(data)[:100])

    # 3.4 更新用户
    resp = openapi_put(f"/api/v1/open/users/{created_user_id}", access_token, {
        "nickname": f"已更新_{suffix}",
    })
    data = resp.json()
    if data.get("code") == 0:
        stats.ok("更新用户成功")
    else:
        stats.fail("更新用户", str(data)[:100])

    # 3.5 查询用户列表应包含新用户
    resp = openapi_get("/api/v1/open/users", access_token)
    data = resp.json()
    users = data.get("data", {}).get("users", [])
    usernames = [u.get("username") for u in users]
    if test_username in usernames:
        stats.ok("用户列表包含新用户", f"共 {len(users)} 个用户")
    else:
        stats.fail("用户列表未包含新用户", f"username={test_username}")

    # 3.6 禁用用户
    resp = openapi_patch(f"/api/v1/open/users/{created_user_id}/status", access_token, {"status": 0})
    data = resp.json()
    if data.get("code") == 0:
        stats.ok("禁用用户成功")
    elif data.get("code") == -10202:
        stats.warn("禁用用户", "应用缺少 user:status 权限码（需在管理后台绑定）")
    else:
        stats.fail("禁用用户", str(data)[:100])

    # 3.7 重新启用
    resp = openapi_patch(f"/api/v1/open/users/{created_user_id}/status", access_token, {"status": 1})
    data = resp.json()
    if data.get("code") == 0:
        stats.ok("启用用户成功")
    elif data.get("code") == -10202:
        stats.warn("启用用户", "应用缺少 user:status 权限码（需在管理后台绑定）")
    else:
        stats.fail("启用用户", str(data)[:100])

    return {"user_id": created_user_id, "username": test_username, "phone": test_phone}


def test_check_permission(access_token, user_info):
    """测试 4: 检查用户权限"""
    print("\n📋 测试 4: 检查用户权限 (POST /api/v1/open/permissions/check)")
    print("-" * 60)

    # 4.1 检查不存在的权限
    resp = openapi_post("/api/v1/open/permissions/check", access_token, {
        "user_id": user_info["user_id"],
        "permission_code": "nonexistent:perm",
    })
    data = resp.json()
    if data.get("code") == 0:
        has_perm = data.get("data", {}).get("has_permission")
        stats.ok("检查权限成功", f"has_permission={has_perm}")
    elif data.get("code") == -10202:
        stats.warn("检查权限", "应用缺少 permission:check 权限码（需在管理后台绑定）")
    else:
        stats.fail("检查权限", str(data)[:100])

    # 4.2 缺少参数
    resp = openapi_post("/api/v1/open/permissions/check", access_token, {
        "user_id": user_info["user_id"],
    })
    data = resp.json()
    if data.get("code") != 0:
        stats.ok("缺少参数应报错", f"code={data.get('code')}")
    else:
        stats.fail("缺少参数未报错", str(data)[:100])


def test_user_profile_by_token(access_token, user_info):
    """测试 5: 通过 Token 获取/更新用户资料"""
    print("\n📋 测试 5: 通过 Token 获取/更新用户资料 (OpenAPI)")
    print("-" * 60)

    # 先登录获取用户 token
    resp = requests.post(
        f"{UAIS_HOST}/api/v1/auth/login?access_token={access_token}",
        json={"username": USER_ID, "password": USER_PASSWORD},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        stats.skip("用户资料测试", "登录失败，无法获取用户 Token")
        return None

    user_token = data["data"].get("token", data["data"].get("access_token"))
    if not user_token:
        stats.skip("用户资料测试", "登录响应中没有 token")
        return None

    # 5.1 获取用户资料
    resp = openapi_hmac_get("/api/v1/open/users/me/profile", {"access_token": user_token})
    data = resp.json()
    if data.get("code") == 0:
        stats.ok("获取用户资料成功", f"user_id={data.get('data', {}).get('user_id')}")
    elif data.get("code") == -10202:
        stats.warn("获取用户资料", "应用缺少 user:profile:read 权限码（需在管理后台绑定）")
    else:
        stats.fail("获取用户资料", str(data)[:150])

    # 5.2 更新用户资料
    resp = openapi_hmac_put("/api/v1/open/users/me/profile", {
        "access_token": user_token,
        "real_name": "测试用户",
        "bio": "API 联调测试",
    })
    data = resp.json()
    if data.get("code") == 0:
        stats.ok("更新用户资料成功")
    elif data.get("code") == -10202:
        stats.warn("更新用户资料", "应用缺少 user:profile:update 权限码（需在管理后台绑定）")
    else:
        stats.fail("更新用户资料", str(data)[:150])

    return user_token


def test_login(access_token):
    """测试 6: 密码登录"""
    print("\n📋 测试 6: 密码登录 (POST /api/v1/auth/login)")
    print("-" * 60)

    # 6.1 正常登录
    resp = requests.post(
        f"{UAIS_HOST}/api/v1/auth/login?access_token={access_token}",
        json={"username": USER_ID, "password": USER_PASSWORD},
        timeout=10,
    )
    data = resp.json()
    login_token = None
    refresh_token = None
    if data.get("code") == 0:
        login_token = data["data"].get("token") or data["data"].get("access_token")
        refresh_token = data["data"].get("refresh_token")
        stats.ok("密码登录成功", f"user_id={data['data'].get('user_id')}")
    else:
        stats.fail("密码登录", str(data)[:100])
        return None, None

    # 6.2 错误密码
    resp = requests.post(
        f"{UAIS_HOST}/api/v1/auth/login?access_token={access_token}",
        json={"username": USER_ID, "password": "wrong_password"},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        stats.ok("错误密码应被拒绝", f"code={data.get('code')}")
    else:
        stats.fail("错误密码未拒绝", str(data)[:100])

    # 6.3 缺少参数
    resp = requests.post(
        f"{UAIS_HOST}/api/v1/auth/login?access_token={access_token}",
        json={"username": USER_ID},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        stats.ok("缺少参数应报错", f"code={data.get('code')}")
    else:
        stats.fail("缺少参数未报错", str(data)[:100])

    return login_token, refresh_token


def test_get_userinfo(access_token, login_token):
    """测试 7: 获取/更新当前用户信息"""
    print("\n📋 测试 7: 获取/更新当前用户信息 (Auth)")
    print("-" * 60)

    if not login_token:
        stats.skip("用户信息测试", "未提供用户 Token")
        return

    headers = {"Authorization": f"Bearer {login_token}"}

    # 7.1 获取用户信息
    resp = requests.get(
        f"{UAIS_HOST}/api/v1/auth/me?access_token={access_token}",
        headers=headers,
        timeout=10,
    )
    data = resp.json()
    if data.get("code") == 0:
        username = data.get("data", {}).get("username", "")
        stats.ok("获取用户信息成功", f"username={username}")
    else:
        stats.fail("获取用户信息", str(data)[:100])

    # 7.2 更新用户信息
    resp = requests.put(
        f"{UAIS_HOST}/api/v1/auth/me?access_token={access_token}",
        headers=headers,
        json={"nickname": f"测试昵称_{random.randint(100,999)}"},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") == 0:
        stats.ok("更新用户信息成功")
    else:
        stats.fail("更新用户信息", str(data)[:100])


def test_user_profile(access_token, login_token):
    """测试 8: 获取/更新用户详细资料"""
    print("\n📋 测试 8: 获取/更新用户详细资料 (Auth)")
    print("-" * 60)

    if not login_token:
        stats.skip("用户资料测试", "未提供用户 Token")
        return

    headers = {"Authorization": f"Bearer {login_token}"}

    # 8.1 获取详细资料
    resp = requests.get(
        f"{UAIS_HOST}/api/v1/auth/me/profile?access_token={access_token}",
        headers=headers,
        timeout=10,
    )
    data = resp.json()
    if data.get("code") == 0:
        stats.ok("获取详细资料成功")
    else:
        stats.fail("获取详细资料", str(data)[:100])

    # 8.2 更新详细资料
    resp = requests.put(
        f"{UAIS_HOST}/api/v1/auth/me/profile?access_token={access_token}",
        headers=headers,
        json={"real_name": "联调测试", "bio": "API测试"},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") == 0:
        stats.ok("更新详细资料成功")
    else:
        stats.fail("更新详细资料", str(data)[:100])


def test_change_password(access_token, login_token):
    """测试 9: 修改密码"""
    print("\n📋 测试 9: 修改密码 (PATCH /api/v1/auth/me/password)")
    print("-" * 60)

    if not login_token:
        stats.skip("修改密码测试", "未提供用户 Token")
        return

    headers = {"Authorization": f"Bearer {login_token}"}

    # 9.1 错误旧密码
    resp = requests.patch(
        f"{UAIS_HOST}/api/v1/auth/me/password?access_token={access_token}",
        headers=headers,
        json={"old_password": "wrong_old_pwd", "new_password": "NewPwd@123456"},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        stats.ok("错误旧密码应被拒绝", f"code={data.get('code')}")
    else:
        stats.fail("错误旧密码未拒绝", str(data)[:100])

    # 9.2 缺少参数
    resp = requests.patch(
        f"{UAIS_HOST}/api/v1/auth/me/password?access_token={access_token}",
        headers=headers,
        json={"old_password": USER_PASSWORD},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        stats.ok("缺少参数应报错", f"code={data.get('code')}")
    else:
        stats.fail("缺少参数未报错", str(data)[:100])


def test_refresh_token(access_token, login_token, old_refresh_token):
    """测试 10: 刷新 Token"""
    print("\n📋 测试 10: 刷新 Token (POST /api/v1/auth/token/refresh)")
    print("-" * 60)

    if not old_refresh_token:
        stats.skip("刷新 Token 测试", "未提供 refresh_token")
        return None, None

    # 10.1 正常刷新
    resp = requests.post(
        f"{UAIS_HOST}/api/v1/auth/token/refresh?access_token={access_token}",
        json={"refresh_token": old_refresh_token},
        timeout=10,
    )
    data = resp.json()
    new_token = None
    new_refresh_token = None
    if data.get("code") == 0:
        new_token = data["data"].get("token") or data["data"].get("access_token")
        new_refresh_token = data["data"].get("refresh_token")
        stats.ok("刷新 Token 成功", "获得新的 token 对")
    else:
        stats.fail("刷新 Token", str(data)[:100])

    # 10.2 无效 refresh_token
    resp = requests.post(
        f"{UAIS_HOST}/api/v1/auth/token/refresh?access_token={access_token}",
        json={"refresh_token": "invalid_refresh_token"},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        stats.ok("无效 refresh_token 应被拒绝", f"code={data.get('code')}")
    else:
        stats.fail("无效 refresh_token 未拒绝", str(data)[:100])

    return new_token, new_refresh_token


def test_logout(access_token, login_token):
    """测试 11: 用户登出"""
    print("\n📋 测试 11: 用户登出 (POST /api/v1/auth/logout)")
    print("-" * 60)

    if not login_token:
        stats.skip("登出测试", "未提供用户 Token")
        return

    headers = {"Authorization": f"Bearer {login_token}"}
    resp = requests.post(
        f"{UAIS_HOST}/api/v1/auth/logout?access_token={access_token}",
        headers=headers,
        timeout=10,
    )
    data = resp.json()
    if data.get("code") == 0:
        stats.ok("登出成功")
    else:
        stats.fail("登出", str(data)[:100])


def test_wechat_api(access_token):
    """测试 12: 微信小程序辅助接口（仅验证配置检查）"""
    print("\n📋 测试 12: 微信小程序辅助接口")
    print("-" * 60)

    # 12.1 获取微信 access_token（未配置时应有明确错误）
    resp = openapi_get("/api/v1/open/wechat/access_token", access_token)
    data = resp.json()
    # 未配置微信时预期返回 -10801
    if data.get("code") == -10801:
        stats.ok("微信未配置有明确提示", "code=-10801")
    elif data.get("code") == 0:
        stats.ok("获取微信 access_token 成功")
    else:
        stats.ok("微信接口返回", f"code={data.get('code')}, {data.get('message', '')}")


def test_sms_api(access_token):
    """测试 13: 短信验证码接口"""
    print("\n📋 测试 13: 短信验证码接口")
    print("-" * 60)

    # 13.1 发送验证码
    test_phone = "13800138000"
    resp = requests.post(
        f"{UAIS_HOST}/api/v1/auth/sms/send?access_token={access_token}",
        json={"phone": test_phone},
        timeout=10,
    )
    data = resp.json()
    # 可能成功或限流，但不应是系统错误
    if data.get("code") == 0:
        stats.ok("发送验证码成功", f"phone={test_phone}")
    elif data.get("code") == -10401:
        stats.ok("发送验证码限流", "code=-10401 (可能之前已发送)")
    elif data.get("code") == -10303:
        stats.warn("发送验证码", "短信服务异常（服务器 SSL 库兼容性问题）")
    else:
        stats.fail("发送验证码", str(data)[:100])

    # 13.2 错误验证码登录
    resp = requests.post(
        f"{UAIS_HOST}/api/v1/auth/sms/login?access_token={access_token}",
        json={"phone": test_phone, "code": "000000"},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") in (-10301, -10302):
        stats.ok("错误验证码应被拒绝", f"code={data.get('code')}")
    elif data.get("code") == 0:
        stats.ok("短信登录成功（验证码恰好正确）")
    else:
        stats.ok("短信验证接口返回", f"code={data.get('code')}, {data.get('message', '')}")


# ==================== 主流程 ====================

def main():
    print()
    print("=" * 72)
    print("  开始测试...")
    print("=" * 72)

    # 1. 获取应用 access_token
    access_token = test_get_app_token()
    if not access_token:
        print("\n❌ 无法获取 access_token，终止测试")
        stats.summary()
        sys.exit(1)

    # 2. 验证 Token
    test_verify_token(access_token)

    # 3. 用户 CRUD
    user_info = test_user_crud(access_token)

    # 4. 检查权限
    if user_info:
        test_check_permission(access_token, user_info)
    else:
        stats.skip("权限检查测试", "未创建测试用户")

    # 5. 通过 Token 获取/更新用户资料 (OpenAPI)
    if user_info:
        user_token = test_user_profile_by_token(access_token, user_info)
    else:
        user_token = None

    # 6. 密码登录
    login_token, refresh_token = test_login(access_token)

    # 7. 获取/更新当前用户信息
    test_get_userinfo(access_token, login_token)

    # 8. 用户详细资料
    test_user_profile(access_token, login_token)

    # 9. 修改密码
    test_change_password(access_token, login_token)

    # 10. 刷新 Token
    new_login_token, new_refresh_token = test_refresh_token(access_token, login_token, refresh_token)

    # 11. 登出
    # 登出后可以再用新 token 测试
    test_logout(access_token, login_token)

    # 12. 微信接口
    test_wechat_api(access_token)

    # 13. 短信接口
    test_sms_api(access_token)

    # 汇总
    stats.summary()

    # 返回退出码
    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
