from rest_framework import serializers


class VerifyTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)


class AppTokenSerializer(serializers.Serializer):
    app_key = serializers.CharField(max_length=64)
    app_secret = serializers.CharField(max_length=128)


class CreateUserSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64, required=False, allow_blank=True, allow_null=True)
    user_type = serializers.ChoiceField(choices=["internal", "external"], default="internal")
    email = serializers.EmailField(max_length=128, required=False, allow_null=True)
    phone = serializers.CharField(max_length=20, required=False, allow_null=True)
    password = serializers.CharField(max_length=256, min_length=8)
    nickname = serializers.CharField(max_length=128, required=False, allow_null=True)
    department = serializers.CharField(max_length=128, required=False, allow_null=True)
    dept_code = serializers.CharField(max_length=64, required=False, allow_null=True)
    role_codes = serializers.ListField(child=serializers.CharField(max_length=64), required=False, default=list)


class UpdateUserSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=128, required=False, allow_null=True)
    email = serializers.EmailField(max_length=128, required=False, allow_null=True)
    phone = serializers.CharField(max_length=20, required=False, allow_null=True)
    avatar = serializers.URLField(max_length=512, required=False, allow_null=True)
    department = serializers.CharField(max_length=128, required=False, allow_null=True)
    dept_code = serializers.CharField(max_length=64, required=False, allow_null=True)
    role_codes = serializers.ListField(child=serializers.CharField(max_length=64), required=False)


class StatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[0, 1])


class CheckPermissionSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    permission_code = serializers.CharField(max_length=64)


class WeChatPhoneSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=512, help_text="微信小程序getPhoneNumber接口返回的code")


class WeChatTokenSerializer(serializers.Serializer):
    app_id = serializers.CharField(max_length=64, required=False, allow_null=True, help_text="微信小程序AppID，不传则使用应用配置的默认AppID")


class ProfileByTokenSerializer(serializers.Serializer):
    access_token = serializers.CharField(max_length=512, help_text="用户的JWT AccessToken")


class UpdateProfileByTokenSerializer(serializers.Serializer):
    access_token = serializers.CharField(max_length=512, help_text="用户的JWT AccessToken")
    avatar = serializers.URLField(max_length=512, required=False, allow_null=True)
    real_name = serializers.CharField(max_length=64, required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=["male", "female", "other"], required=False, allow_null=True)
    birthday = serializers.DateField(required=False, allow_null=True)
    id_card = serializers.CharField(max_length=32, required=False, allow_null=True)
    nationality = serializers.CharField(max_length=64, required=False, allow_null=True)
    address = serializers.CharField(max_length=512, required=False, allow_null=True)
    zip_code = serializers.CharField(max_length=20, required=False, allow_null=True)
    emergency_contact = serializers.CharField(max_length=64, required=False, allow_null=True)
    emergency_phone = serializers.CharField(max_length=20, required=False, allow_null=True)
    job_title = serializers.CharField(max_length=128, required=False, allow_null=True)
    company = serializers.CharField(max_length=256, required=False, allow_null=True)
    employee_id = serializers.CharField(max_length=64, required=False, allow_null=True)
    hire_date = serializers.DateField(required=False, allow_null=True)
    work_email = serializers.EmailField(max_length=128, required=False, allow_null=True)
    work_phone = serializers.CharField(max_length=32, required=False, allow_null=True)
    wechat = serializers.CharField(max_length=64, required=False, allow_null=True)
    qq = serializers.CharField(max_length=32, required=False, allow_null=True)
    weibo = serializers.CharField(max_length=128, required=False, allow_null=True)
    bio = serializers.CharField(max_length=2000, required=False, allow_null=True)
    interests = serializers.CharField(max_length=512, required=False, allow_null=True)
    tags = serializers.JSONField(required=False, allow_null=True)
    extra_data = serializers.JSONField(required=False, allow_null=True)
