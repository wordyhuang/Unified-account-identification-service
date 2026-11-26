import uuid

from django.db import models
from apps.accounts.models import User


class UserAppAccess(models.Model):
    STATUS_CHOICES = (
        ("active", "有效"),
        ("revoked", "已撤销"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="app_accesses")
    app = models.ForeignKey("applications.Application", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="granted_accesses",
    )

    class Meta:
        db_table = "user_app_access"
        unique_together = [("user", "app")]
        verbose_name = "用户应用访问授权"

    def __str__(self):
        return f"{self.user.username} -> {self.app.name}: {self.status}"


class UserGroup(models.Model):
    """用户组：租户内的用户集合，作为应用准入的批量边界。

    与角色（RBAC API 权限）、部门（组织树）、标签（业务标记）语义独立。
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, verbose_name="UUID")
    tenant = models.ForeignKey("accounts.Tenant", on_delete=models.CASCADE, verbose_name="所属企业")
    name = models.CharField(max_length=64, verbose_name="组名称")
    code = models.CharField(max_length=64, blank=True, default="", verbose_name="组编码")
    description = models.CharField(max_length=256, blank=True, default="", verbose_name="描述")
    status = models.BooleanField(default=True, verbose_name="状态")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_group"
        unique_together = [("tenant", "name")]
        verbose_name = "用户组"

    def __str__(self):
        return self.name


class UserGroupMember(models.Model):
    """用户组成员关系（成员必须与组同租户，由应用层校验）。"""
    group = models.ForeignKey(
        UserGroup, on_delete=models.CASCADE, related_name="members", verbose_name="用户组"
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE,
        related_name="group_memberships", verbose_name="用户",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_group_member"
        unique_together = [("group", "user")]
        verbose_name = "用户组成员"

    def __str__(self):
        return f"{self.group.name} <- {self.user.username}"


class AppGroupBinding(models.Model):
    """应用绑定的准入用户组（应用与组必须同租户，由应用层校验）。"""
    app = models.ForeignKey(
        "applications.Application", on_delete=models.CASCADE,
        related_name="group_bindings", verbose_name="应用",
    )
    group = models.ForeignKey(
        UserGroup, on_delete=models.CASCADE,
        related_name="app_bindings", verbose_name="用户组",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "app_group_binding"
        unique_together = [("app", "group")]
        verbose_name = "应用准入组绑定"

    def __str__(self):
        return f"{self.app.name} -> {self.group.name}"
