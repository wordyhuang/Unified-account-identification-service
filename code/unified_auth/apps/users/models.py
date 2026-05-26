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
