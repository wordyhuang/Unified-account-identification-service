from rest_framework import serializers
from .models import User, UserProfile


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=256)


class SmsSendSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    app_key = serializers.CharField(max_length=64, required=False, allow_null=True)


class SmsLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=10)


class SmsVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=10)


class SocialLoginSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(
        choices=["wechat_mp", "wechat_web", "dingtalk", "feishu"]
    )
    code = serializers.CharField(max_length=512)
    app_key = serializers.CharField(max_length=64, required=False, allow_null=True)


class WechatLoginSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=512)
    app_key = serializers.CharField(max_length=64, required=False, allow_null=True)


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(max_length=512)


class UserInfoSerializer(serializers.ModelSerializer):
    tags = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "uuid", "user_type", "username", "email", "phone",
            "nickname", "avatar", "department", "status",
            "tenant_id", "last_login_at", "created_at", "tags", "company",
        ]

    def get_tags(self, obj):
        from apps.tags.models import UserTagBinding
        bindings = UserTagBinding.objects.filter(user=obj)
        return [b.tag.name for b in bindings]

    def get_company(self, obj):
        try:
            return obj.profile.company
        except AttributeError:
            return None


class UpdateUserInfoSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=128, required=False)
    email = serializers.EmailField(max_length=128, required=False)
    phone = serializers.CharField(max_length=20, required=False)
    avatar = serializers.URLField(max_length=512, required=False)
    company = serializers.CharField(max_length=256, required=False, allow_null=True)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(max_length=256)
    new_password = serializers.CharField(max_length=256, min_length=8)


class PwdResetSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=10)
    new_password = serializers.CharField(max_length=256, min_length=8)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "id", "avatar", "real_name", "gender", "birthday", "id_card", "nationality",
            "address", "zip_code", "emergency_contact", "emergency_phone",
            "job_title", "company", "employee_id", "hire_date", "work_email", "work_phone",
            "wechat", "qq", "weibo", "bio", "interests", "tags", "extra_data",
            "created_at", "updated_at",
        ]


class UpdateUserProfileSerializer(serializers.Serializer):
    # 基本信息
    avatar = serializers.URLField(max_length=512, required=False, allow_null=True)
    real_name = serializers.CharField(max_length=64, required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=["male", "female", "other"], required=False, allow_null=True
    )
    birthday = serializers.DateField(required=False, allow_null=True)
    id_card = serializers.CharField(max_length=32, required=False, allow_null=True)
    nationality = serializers.CharField(max_length=64, required=False, allow_null=True)

    # 联系信息
    address = serializers.CharField(max_length=512, required=False, allow_null=True)
    zip_code = serializers.CharField(max_length=20, required=False, allow_null=True)
    emergency_contact = serializers.CharField(max_length=64, required=False, allow_null=True)
    emergency_phone = serializers.CharField(max_length=20, required=False, allow_null=True)

    # 工作信息
    job_title = serializers.CharField(max_length=128, required=False, allow_null=True)
    company = serializers.CharField(max_length=256, required=False, allow_null=True)
    employee_id = serializers.CharField(max_length=64, required=False, allow_null=True)
    hire_date = serializers.DateField(required=False, allow_null=True)
    work_email = serializers.EmailField(max_length=128, required=False, allow_null=True)
    work_phone = serializers.CharField(max_length=32, required=False, allow_null=True)

    # 社交信息
    wechat = serializers.CharField(max_length=64, required=False, allow_null=True)
    qq = serializers.CharField(max_length=32, required=False, allow_null=True)
    weibo = serializers.CharField(max_length=128, required=False, allow_null=True)

    # 扩展信息
    bio = serializers.CharField(max_length=2000, required=False, allow_null=True)
    interests = serializers.CharField(max_length=512, required=False, allow_null=True)
    tags = serializers.JSONField(required=False, allow_null=True)
    extra_data = serializers.JSONField(required=False, allow_null=True)
