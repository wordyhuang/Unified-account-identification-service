import pytest
import jwt
from datetime import datetime, timezone, timedelta
from django.conf import settings
from common.utils import create_access_token, decode_access_token


@pytest.mark.django_db
class TestTokenConsistency:
    
    def test_same_payload_generates_same_token(self):
        """验证相同的payload在同一时间生成相同的token"""
        payload1 = {"user_id": 1, "tenant_id": 1, "user_type": "internal"}
        payload2 = {"user_id": 1, "tenant_id": 1, "user_type": "internal"}
        
        token1 = create_access_token(payload1)
        token2 = create_access_token(payload2)
        
        decoded1 = decode_access_token(token1)
        decoded2 = decode_access_token(token2)
        
        assert decoded1["user_id"] == decoded2["user_id"]
        assert decoded1["tenant_id"] == decoded2["tenant_id"]
        assert decoded1["user_type"] == decoded2["user_type"]
    
    def test_different_users_generate_different_tokens(self):
        """验证不同用户生成的token解码后包含不同的用户信息"""
        payload1 = {"user_id": 1, "tenant_id": 1, "user_type": "internal"}
        payload2 = {"user_id": 2, "tenant_id": 1, "user_type": "external"}
        
        token1 = create_access_token(payload1)
        token2 = create_access_token(payload2)
        
        decoded1 = decode_access_token(token1)
        decoded2 = decode_access_token(token2)
        
        assert decoded1["user_id"] != decoded2["user_id"]
        assert decoded1["user_type"] != decoded2["user_type"]
    
    def test_token_contains_required_claims(self):
        """验证token包含必需的声明字段"""
        payload = {"user_id": 1, "tenant_id": 1, "user_type": "internal"}
        token = create_access_token(payload)
        decoded = decode_access_token(token)
        
        assert "user_id" in decoded
        assert "tenant_id" in decoded
        assert "user_type" in decoded
        assert "exp" in decoded
        assert "iat" in decoded
    
    def test_token_expiration_is_set(self):
        """验证token设置了正确的过期时间"""
        payload = {"user_id": 1, "tenant_id": 1, "user_type": "internal"}
        token = create_access_token(payload)
        decoded = decode_access_token(token)
        
        exp_time = datetime.fromtimestamp(decoded["exp"], timezone.utc)
        iat_time = datetime.fromtimestamp(decoded["iat"], timezone.utc)
        
        expected_exp = iat_time + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        assert (exp_time - expected_exp).total_seconds() < 1
