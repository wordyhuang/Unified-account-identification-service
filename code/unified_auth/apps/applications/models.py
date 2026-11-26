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
    # 邀请注册页接入：三个地址的 origin 必须命中 callback_urls 白名单
    registration_page_url = models.URLField(max_length=512, blank=True, default="", verbose_name="邀请注册页地址")
    registration_success_url = models.URLField(max_length=512, blank=True, default="", verbose_name="注册成功跳转地址")
    webhook_url = models.URLField(max_length=512, blank=True, default="", verbose_name="注册事件回调地址")
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


class WebhookDelivery(models.Model):
    """Webhook 投递记录：每次尝试落库，便于排查与后续重放。"""
    STATUS_CHOICES = (
        ("pending", "待投递"),
        ("success", "成功"),
        ("failed", "失败"),
    )

    app = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="webhook_deliveries")
    tenant = models.ForeignKey("accounts.Tenant", on_delete=models.CASCADE)
    event = models.CharField(max_length=64, verbose_name="事件类型")
    event_id = models.UUIDField(unique=True, verbose_name="事件ID（幂等键）")
    url = models.URLField(max_length=512, verbose_name="回调地址")
    payload = CompatibleJSONField(null=True, blank=True, verbose_name="载荷")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending", verbose_name="状态")
    attempts = models.PositiveIntegerField(default=0, verbose_name="尝试次数")
    last_status_code = models.IntegerField(null=True, blank=True, verbose_name="最近状态码")
    last_error = models.TextField(null=True, blank=True, verbose_name="最近错误")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "webhook_delivery"
        verbose_name = "Webhook 投递记录"
        ordering = ["-created_at"]


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
