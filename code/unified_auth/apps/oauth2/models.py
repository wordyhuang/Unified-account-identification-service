from django.db import models
from django.utils import timezone
from apps.applications.models import Application
from apps.accounts.models import User


class AuthCode(models.Model):
    code = models.CharField(max_length=64, unique=True, verbose_name="授权码")
    app = models.ForeignKey(Application, on_delete=models.CASCADE, verbose_name="所属应用")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="授权用户")
    redirect_uri = models.URLField(verbose_name="回调地址")
    state = models.CharField(max_length=256, null=True, blank=True, verbose_name="CSRF状态码")
    expires_at = models.DateTimeField(verbose_name="过期时间")
    is_used = models.BooleanField(default=False, verbose_name="是否已使用")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auth_code"
        verbose_name = "授权码"

    def __str__(self):
        return f"{self.code[:16]}...({self.app.name})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=["is_used"])