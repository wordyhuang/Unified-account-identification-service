import os
from django.core.management.base import BaseCommand
from apps.accounts.models import Tenant, User
from apps.rbac.models import ApiPermission, Role, RolePermission


PERMISSIONS = [
    {"code": "token:verify", "name": "验证Token", "description": "验证用户身份Token的有效性，用于开放API的Token认证", "method": "POST", "path": "/api/v1/open/verify_token", "category": "auth"},
    {"code": "user:read", "name": "读取用户", "description": "查询和获取用户的基本信息，支持按条件筛选和分页", "method": "GET", "path": "/api/v1/open/users", "category": "user"},
    {"code": "user:create", "name": "创建用户", "description": "在指定租户下创建新的用户账号", "method": "POST", "path": "/api/v1/open/users", "category": "user"},
    {"code": "user:update", "name": "修改用户", "description": "更新现有用户的信息，如昵称、邮箱、手机号等", "method": "PUT", "path": "/api/v1/open/users/:id", "category": "user"},
    {"code": "permission:check", "name": "校验权限", "description": "校验用户是否拥有指定的操作权限", "method": "POST", "path": "/api/v1/open/check_permission", "category": "permission"},
]


class Command(BaseCommand):
    help = "初始化系统预置数据"

    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(
            slug="default",
            defaults={"name": "默认企业"},
        )
        self.stdout.write(f"Tenant: {tenant.name}")

        for perm in PERMISSIONS:
            obj, created = ApiPermission.objects.get_or_create(
                code=perm["code"],
                defaults=perm,
            )
            if not created:
                for k, v in perm.items():
                    setattr(obj, k, v)
                obj.save(update_fields=[k for k in perm.keys() if k != "code"])
        self.stdout.write(f"Created {len(PERMISSIONS)} permissions")

        admin_role, _ = Role.objects.get_or_create(
            tenant=tenant, code="admin",
            defaults={"name": "管理员"},
        )
        all_perms = ApiPermission.objects.all()
        for perm in all_perms:
            RolePermission.objects.get_or_create(
                role=admin_role, permission=perm
            )
        self.stdout.write(f"Admin role: {admin_role.name} with {all_perms.count()} permissions")

        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin",
                password=os.getenv("ADMIN_INIT_PASSWORD", "admin123456"),
            )
            self.stdout.write("Created default admin: admin")
        else:
            self.stdout.write("Admin user already exists, skipped")

        self.stdout.write(self.style.SUCCESS("Init complete"))
