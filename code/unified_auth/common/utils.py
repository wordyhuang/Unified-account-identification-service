import jwt
import json
import os
from datetime import datetime, timedelta, timezone
from django.conf import settings


def create_access_token(payload: dict) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    data["iat"] = datetime.now(timezone.utc)
    return jwt.encode(data, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def generate_refresh_token() -> str:
    import uuid
    return uuid.uuid4().hex


def verify_signature(app_secret: str, params: dict, timestamp: str, signature: str) -> bool:
    import hmac
    import hashlib
    message = f"{params}{timestamp}".encode("utf-8")
    expected = hmac.new(
        app_secret.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def get_superadmin_accounts() -> list:
    """
    从环境变量获取超级管理员账户列表
    返回: [{"username": str, "password": str}, ...]
    """
    accounts_json = os.getenv("SUPERADMIN_ACCOUNTS", "[]")
    try:
        accounts = json.loads(accounts_json)
        if not isinstance(accounts, list):
            return []
        return accounts
    except (json.JSONDecodeError, ValueError):
        return []


def is_superadmin_credentials(username: str, password: str) -> dict or None:
    """
    验证是否为超级管理员登录
    返回: 超级管理员信息 dict，否则 None
    """
    accounts = get_superadmin_accounts()
    for account in accounts:
        if account.get("username") == username and account.get("password") == password:
            return {
                "username": username,
                "is_superadmin": True
            }
    return None
