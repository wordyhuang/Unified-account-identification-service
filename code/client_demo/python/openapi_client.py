#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一账户认证服务 - OpenAPI Python SDK

基于 API 对接文档 v2.0 生成
文档: document/gateway_openapi_documentation_v2.md

使用方式:
    pip install requests
    
    # 初始化客户端
    client = OpenAPIClient(
        app_key="你的APP_KEY",
        app_secret="你的APP_SECRET",
        base_url="http://localhost:8000"
    )
    
    # 调用 API
    result = client.verify_token("user_jwt_token")
    users = client.list_users()
"""
import hashlib
import hmac
import time

import requests


class OpenAPIClient:
    """统一账户认证服务 OpenAPI 客户端"""

    def __init__(self, app_key, app_secret, base_url="http://localhost:8000"):
        """
        初始化客户端
        
        Args:
            app_key: 应用唯一标识（管理后台获取）
            app_secret: 应用密钥（创建时显示一次）
            base_url: 服务地址，默认 http://localhost:8000
        """
        self.app_key = app_key
        # 签名使用 app_secret 的 SHA256 哈希值
        self.app_secret_hash = hashlib.sha256(app_secret.encode()).hexdigest()
        self.base_url = base_url.rstrip("/")

    def _generate_signature(self, timestamp):
        """
        生成 HMAC-SHA256 签名
        
        签名公式: HMAC-SHA256(app_secret_hash, "{}" + timestamp)
        
        Args:
            timestamp: Unix 时间戳字符串（秒）
        
        Returns:
            十六进制签名字符串
        """
        message = f"{{}}{timestamp}".encode("utf-8")
        return hmac.new(
            self.app_secret_hash.encode("utf-8"),
            message,
            hashlib.sha256,
        ).hexdigest()

    def _build_headers(self):
        """
        构建 OpenAPI 请求头
        
        Returns:
            请求头字典
        """
        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp)

        headers = {
            "Content-Type": "application/json",
            "X-App-Key": self.app_key,
            "X-Timestamp": timestamp,
            "X-Signature": signature,
        }
        return headers

    def _request(self, method, path, body=None):
        """
        发送 API 请求
        
        Args:
            method: HTTP 方法（GET/POST/PUT/PATCH/DELETE）
            path: API 路径，如 /api/v1/open/users
            body: 请求体（dict）
        
        Returns:
            解析后的 JSON 响应
        
        Raises:
            requests.RequestException: 网络请求异常
        """
        url = f"{self.base_url}{path}"
        headers = self._build_headers()
        kwargs = {"headers": headers}

        if body is not None:
            kwargs["json"] = body

        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    # ==================== 开放 API（OpenAPI） ====================

    def verify_token(self, token):
        """验证用户 Token 的有效性"""
        return self._request("POST", "/api/v1/open/verify_token", {"token": token})

    def list_users(self):
        """查询当前租户下的用户列表"""
        return self._request("GET", "/api/v1/open/users")

    def create_user(self, username, password, user_type="internal", **kwargs):
        """
        创建新用户
        
        Args:
            username: 用户名（必填）
            password: 密码（必填，8-256字符）
            user_type: 用户类型，internal/external，默认 internal
            **kwargs: 可选字段
                - email: 邮箱
                - phone: 手机号
                - nickname: 昵称
                - department: 部门名称
                - dept_code: 部门编码
                - role_codes: 角色编码列表
        """
        body = {
            "username": username,
            "password": password,
            "user_type": user_type,
        }
        body.update(kwargs)
        return self._request("POST", "/api/v1/open/users", body)

    def get_user(self, user_id):
        """获取单个用户详情"""
        return self._request("GET", f"/api/v1/open/users/{user_id}")

    def update_user(self, user_id, **kwargs):
        """
        更新用户信息
        
        Args:
            user_id: 用户 ID
            **kwargs: 可更新字段
                - nickname: 昵称
                - email: 邮箱
                - phone: 手机号
                - avatar: 头像 URL
                - department: 部门名称
                - dept_code: 部门编码
                - role_codes: 角色编码列表
        """
        return self._request("PUT", f"/api/v1/open/users/{user_id}", kwargs)

    def toggle_user_status(self, user_id, status):
        """
        启用/禁用用户
        
        Args:
            user_id: 用户 ID
            status: 0=禁用，1=启用
        """
        return self._request("PATCH", f"/api/v1/open/users/{user_id}/status", {"status": status})

    def check_permission(self, user_id, permission_code):
        """检查用户是否具有指定权限"""
        return self._request(
            "POST",
            "/api/v1/open/check_permission",
            {"user_id": user_id, "permission_code": permission_code},
        )

    # ==================== 用户认证 API（Auth） ====================

    def login(self, username, password):
        """用户名密码登录"""
        return self._request("POST", "/api/v1/auth/login", {
            "username": username,
            "password": password,
        })

    def sms_send(self, phone):
        """发送短信验证码"""
        return self._request("POST", "/api/v1/auth/sms/send", {"phone": phone})

    def sms_login(self, phone, code):
        """短信验证码登录"""
        return self._request("POST", "/api/v1/auth/sms/login", {
            "phone": phone,
            "code": code,
        })

    def social_login(self, provider, code):
        """
        社交登录
        
        Args:
            provider: 第三方平台（wechat_mp/wechat_web/dingtalk/feishu）
            code: 第三方授权码
        """
        return self._request("POST", "/api/v1/auth/social/login", {
            "provider": provider,
            "code": code,
        })

    def refresh_token(self, refresh_token):
        """刷新 Token"""
        return self._request("POST", "/api/v1/auth/refresh", {
            "refresh_token": refresh_token,
        })

    def get_userinfo(self, access_token):
        """获取当前登录用户信息"""
        headers = self._build_headers()
        headers["Authorization"] = f"Bearer {access_token}"
        url = f"{self.base_url}/api/v1/auth/userinfo"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def update_userinfo(self, access_token, **kwargs):
        """更新当前登录用户个人信息"""
        headers = self._build_headers()
        headers["Authorization"] = f"Bearer {access_token}"
        url = f"{self.base_url}/api/v1/auth/userinfo"
        response = requests.put(url, headers=headers, json=kwargs)
        response.raise_for_status()
        return response.json()

    def change_password(self, access_token, old_password, new_password):
        """修改密码"""
        body = {"old_password": old_password, "new_password": new_password}
        headers = self._build_headers()
        headers["Authorization"] = f"Bearer {access_token}"
        url = f"{self.base_url}/api/v1/auth/userinfo/password"
        response = requests.patch(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()

    def logout(self, access_token):
        """用户登出"""
        headers = self._build_headers()
        headers["Authorization"] = f"Bearer {access_token}"
        url = f"{self.base_url}/api/v1/auth/logout"
        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()


# ==================== 使用示例 ====================

def main():
    """完整的 API 调用示例"""
    APP_KEY = "efc44f100f59fa0e08c1986715f587df"
    APP_SECRET = "ef276bb188138dcf6eaa3e958d82cbb91bd15f494df4b9ef3a5dffcc590c97c4"
    BASE_URL = "http://localhost:8000"

    client = OpenAPIClient(APP_KEY, APP_SECRET, BASE_URL)

    print("=" * 72)
    print("  统一账户认证服务 - OpenAPI 调用示例")
    print("=" * 72)

    # 1. 验证 Token（使用无效 Token 演示）
    print("\n[1/5] 验证 Token ...")
    result = client.verify_token("invalid_jwt_token")
    print(f"      结果: valid={result.get('data', {}).get('valid')}")
    print(f"      message: {result.get('message')}")

    # 2. 查询用户列表
    print("\n[2/5] 查询用户列表 ...")
    result = client.list_users()
    users = result.get("data", {}).get("users", [])
    print(f"      共 {len(users)} 个用户")
    for u in users[:3]:
        print(f"      - ID={u['id']}, username={u['username']}, email={u.get('email', '-')}")

    # 3. 创建新用户
    print("\n[3/5] 创建新用户 ...")
    import random
    suffix = random.randint(1000, 9999)
    result = client.create_user(
        username=f"api_demo_{suffix}",
        password="Demo@123456",
        user_type="internal",
        email=f"demo_{suffix}@example.com",
        phone=f"138{suffix:08d}",
        nickname=f"演示用户{suffix}",
    )
    if result.get("code") == 0:
        new_user_id = result["data"]["id"]
        print(f"      创建成功: ID={new_user_id}, username=api_demo_{suffix}")

        # 4. 更新用户
        print("\n[4/5] 更新用户信息 ...")
        result = client.update_user(new_user_id, nickname=f"已更新-演示用户{suffix}")
        print(f"      更新结果: {result.get('message')}")

        # 5. 检查权限
        print("\n[5/5] 检查权限 (user:read) ...")
        result = client.check_permission(new_user_id, "user:read")
        data = result.get("data", {})
        print(f"      用户 ID={data.get('user_id')}")
        print(f"      权限编码={data.get('permission_code')}")
        print(f"      是否有权限={data.get('has_permission')}")
    else:
        print(f"      创建失败: {result.get('message')}")

    print("\n" + "=" * 72)
    print("  示例执行完毕")
    print("=" * 72)


if __name__ == "__main__":
    main()
