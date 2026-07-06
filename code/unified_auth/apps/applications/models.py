import uuid

from django.db import models
from common.fields import CompatibleJSONField


class Application(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, verbose_name="UUID")
    tenant = models.ForeignKey("accounts.Tenant", on_delete=models.CASCADE)
    name = models.CharField(max_length=128, verbose_name="应用名称")
    app_key = models.CharField(max_length=64, unique=True, verbose_name="AppKey")
    app_secret = models.CharField(max_length=256, verbose_name="AppSecret")
    callback_urls = CompatibleJSONField(null=True, blank=True, verbose_name="回调地址列表")
    default_access_user_types = CompatibleJSONField(
        null=True, blank=True, default=list,
        verbose_name="默认允许访问的用户类型",
        help_text='例如: ["internal", "external"]',
    )

    # 微信登录配置
    wechat_mp_app_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="微信小程序AppID")
    wechat_mp_app_secret = models.CharField(max_length=256, null=True, blank=True, verbose_name="微信小程序AppSecret")
    wechat_web_app_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="微信网页AppID")
    wechat_web_app_secret = models.CharField(max_length=256, null=True, blank=True, verbose_name="微信网页AppSecret")

    status = models.BooleanField(default=True, verbose_name="状态")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "application"
        verbose_name = "接入应用"

    def __str__(self):
        return self.name


class AppApiCallStat(models.Model):
    app = models.ForeignKey(Application, on_delete=models.CASCADE, db_index=True)
    tenant = models.ForeignKey("accounts.Tenant", on_delete=models.CASCADE, db_index=True)
    api_path = models.CharField(max_length=255, db_index=True)
    call_date = models.DateField(db_index=True)
    call_count = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "app_api_call_stat"
        unique_together = ("app", "api_path", "call_date")
        verbose_name = "应用API调用统计"


class TenantApiCallStat(models.Model):
    tenant = models.ForeignKey("accounts.Tenant", on_delete=models.CASCADE, db_index=True)
    api_path = models.CharField(max_length=255, db_index=True)
    call_date = models.DateField(db_index=True)
    call_count = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "tenant_api_call_stat"
        unique_together = ("tenant", "api_path", "call_date")
        verbose_name = "租户API调用统计"
