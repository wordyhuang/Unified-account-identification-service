from rest_framework import serializers


class VerifyTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)


class CreateUserSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64)
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
