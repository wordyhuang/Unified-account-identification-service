from django.db import models


class ApiPermission(models.Model):
    code = models.CharField(max_length=64, unique=True, verbose_name="权限码")
    name = models.CharField(max_length=128, verbose_name="权限名称")
    method = models.CharField(max_length=10, verbose_name="HTTP方法")
    path = models.CharField(max_length=256, verbose_name="API路径")
    category = models.CharField(max_length=32, verbose_name="分类")
    description = models.CharField(max_length=512, null=True, blank=True)

    class Meta:
        db_table = "api_permission"
        verbose_name = "API权限"

    def __str__(self):
        return f"{self.code}({self.method} {self.path})"


class Role(models.Model):
    tenant = models.ForeignKey("accounts.Tenant", on_delete=models.CASCADE)
    name = models.CharField(max_length=64, verbose_name="角色名称")
    code = models.CharField(max_length=64, verbose_name="角色编码")
    permissions = models.ManyToManyField(
        ApiPermission, through="RolePermission", verbose_name="权限"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "role"
        verbose_name = "角色"

    def __str__(self):
        return self.name


class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(ApiPermission, on_delete=models.CASCADE)

    class Meta:
        db_table = "role_permission"
        unique_together = [("role", "permission")]


class UserRole(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        db_table = "user_role"
        unique_together = [("user", "role")]


class AppRoleBinding(models.Model):
    app = models.ForeignKey("applications.Application", on_delete=models.CASCADE)
    permission = models.ForeignKey(ApiPermission, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_role_binding"
        unique_together = [("app", "permission")]
        verbose_name = "应用权限绑定"
