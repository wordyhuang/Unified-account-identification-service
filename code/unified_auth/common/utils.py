import jwt
import json
import os
import bcrypt
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


def generate_refresh_token(payload: dict) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    data["iat"] = datetime.now(timezone.utc)
    data["token_type"] = "refresh"
    return jwt.encode(data, settings.JWT_SECRET_KEY, algorithm="HS256")


def verify_signature(app_secret: str, params: dict, timestamp: str, signature: str) -> bool:
    import hmac
    import hashlib
    
    normalized_params = _normalize_params(params)
    message = f"{normalized_params}{timestamp}".encode("utf-8")
    expected = hmac.new(
        app_secret.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _normalize_params(params: dict) -> str:
    """
    规范化参数用于签名验证
    返回JSON格式字符串，保持与原有签名方式兼容
    """
    import json
    if not params:
        return "{}"
    return json.dumps(params, ensure_ascii=False, separators=(",", ":"))


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
    
    支持两种密码格式：
    1. bcrypt 哈希密码（推荐）- 以 '$2b$' 或 '$2a$' 开头
    2. 明文密码（向后兼容，不推荐）
    """
    accounts = get_superadmin_accounts()
    for account in accounts:
        if account.get("username") != username:
            continue
        
        stored_password = account.get("password", "")
        
        if stored_password.startswith(('$2b$', '$2a$')):
            if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                return {
                    "username": username,
                    "is_superadmin": True
                }
        elif stored_password == password:
            return {
                "username": username,
                "is_superadmin": True
            }
    
    return None


def hash_superadmin_password(password: str) -> str:
    """
    使用 bcrypt 哈希密码，用于生成超级管理员配置密码
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
