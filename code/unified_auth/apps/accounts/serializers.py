from rest_framework import serializers
from .models import User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=256)


class SmsSendSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)


class SmsLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=10)


class SocialLoginSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(
        choices=["wechat_mp", "wechat_web", "dingtalk", "feishu"]
    )
    code = serializers.CharField(max_length=512)


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(max_length=64)


class UserInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "user_type", "username", "email", "phone",
            "nickname", "avatar", "department", "status",
            "tenant_id", "last_login_at", "created_at",
        ]


class UpdateUserInfoSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=128, required=False)
    email = serializers.EmailField(max_length=128, required=False)
    phone = serializers.CharField(max_length=20, required=False)
    avatar = serializers.URLField(max_length=512, required=False)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(max_length=256)
    new_password = serializers.CharField(max_length=256, min_length=8)
