from django.db import models
from common.fields import CompatibleJSONField


class AuditLog(models.Model):
    tenant = models.ForeignKey("accounts.Tenant", on_delete=models.CASCADE, null=True, blank=True)
    actor_id = models.BigIntegerField(null=True, blank=True, verbose_name="操作人ID")
    actor_name = models.CharField(max_length=64, null=True, blank=True, verbose_name="操作人")
    action = models.CharField(max_length=64, verbose_name="操作类型")
    resource_type = models.CharField(max_length=32, null=True, blank=True, verbose_name="资源类型")
    resource_id = models.BigIntegerField(null=True, blank=True, verbose_name="资源ID")
    detail = CompatibleJSONField(null=True, blank=True, verbose_name="详情")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        verbose_name = "审计日志"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.created_at}] {self.actor_name} - {self.action}"
