from django.db import models
import uuid


class UserTag(models.Model):
    """用户标签定义"""
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, verbose_name="UUID")
    tenant = models.ForeignKey(
        "accounts.Tenant", on_delete=models.CASCADE, verbose_name="所属企业"
    )
    name = models.CharField(max_length=64, verbose_name="标签名称")
    color = models.CharField(max_length=7, default="#1890ff", verbose_name="标签颜色")
    description = models.CharField(max_length=256, null=True, blank=True, verbose_name="标签描述")
    status = models.BooleanField(default=True, verbose_name="状态")
    sort_order = models.IntegerField(default=0, verbose_name="排序")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_tag"
        verbose_name = "用户标签"
        unique_together = [("tenant", "name")]

    def __str__(self):
        return self.name


class UserTagBinding(models.Model):
    """用户标签绑定关系"""
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="tag_bindings", verbose_name="关联用户"
    )
    tag = models.ForeignKey(
        UserTag, on_delete=models.CASCADE, related_name="user_bindings", verbose_name="关联标签"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_tag_binding"
        verbose_name = "用户标签绑定"
        unique_together = [("user", "tag")]

    def __str__(self):
        return f"{self.user.username} -> {self.tag.name}"