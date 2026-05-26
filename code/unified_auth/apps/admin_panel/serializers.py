import csv
import io
from rest_framework import serializers
from apps.accounts.models import User, Tenant, Department
from apps.applications.models import Application
from apps.rbac.models import Role, ApiPermission, AppRoleBinding


class SuperAdminCreateTenantSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    slug = serializers.SlugField(max_length=64)


class SuperAdminUpdateTenantSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128, required=False)
    slug = serializers.SlugField(max_length=64, required=False)
    status = serializers.BooleanField(required=False)


class AdminCreateUserSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=256, min_length=8)
    user_type = serializers.ChoiceField(choices=["internal", "external"])
    nickname = serializers.CharField(max_length=128, required=False, allow_null=True)
    email = serializers.EmailField(max_length=128, required=False, allow_null=True)
    phone = serializers.CharField(max_length=20, required=False, allow_null=True)
    department = serializers.CharField(max_length=128, required=False, allow_null=True)
    dept_id = serializers.IntegerField(required=False, allow_null=True)


class AdminUpdateUserSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=128, required=False, allow_null=True)
    email = serializers.EmailField(max_length=128, required=False, allow_null=True)
    phone = serializers.CharField(max_length=20, required=False, allow_null=True)
    department = serializers.CharField(max_length=128, required=False, allow_null=True)
    dept_id = serializers.IntegerField(required=False, allow_null=True)


class AdminUserStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[0, 1])


class AdminResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(max_length=256, min_length=8)


class AdminCreateAppSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    callback_urls = serializers.ListField(child=serializers.URLField(), required=False, allow_null=True)
    default_access_user_types = serializers.ListField(
        child=serializers.ChoiceField(choices=["internal", "external"]),
        required=False, allow_null=True,
    )


class AdminUpdateAppSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128, required=False)
    callback_urls = serializers.ListField(child=serializers.URLField(), required=False, allow_null=True)
    default_access_user_types = serializers.ListField(
        child=serializers.ChoiceField(choices=["internal", "external"]),
        required=False, allow_null=True,
    )
    permission_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_null=True)


class AdminAppStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[True, False])


class AdminCreateRoleSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    code = serializers.CharField(max_length=64)
    permission_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class AdminUpdateRoleSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64, required=False)
    permission_ids = serializers.ListField(child=serializers.IntegerField(), required=False)


class AdminBatchUserStatusSerializer(serializers.Serializer):
    user_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    status = serializers.ChoiceField(choices=[0, 1])


class AdminBatchUserDeleteSerializer(serializers.Serializer):
    user_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class AdminDepartmentSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    sort_order = serializers.IntegerField(required=False, default=0)


class AdminDepartmentUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128, required=False)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    sort_order = serializers.IntegerField(required=False)


class AdminAppPermissionSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(child=serializers.IntegerField(), min_length=0)


class AdminCopyRoleSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=64)
    code = serializers.CharField(max_length=64)


class AdminUserImportSerializer(serializers.Serializer):
    csv_content = serializers.CharField()


class AdminImpersonateSerializer(serializers.Serializer):
    tenant_id = serializers.IntegerField()
