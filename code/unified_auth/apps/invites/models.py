import secrets

from django.db import models

from apps.accounts.models import Tenant, User
from common.fields import CompatibleJSONField


def generate_code(length=32):
    """生成凭证码长码（hex 字符串）"""
    return secrets.token_hex(length // 2)


def generate_short_code(length=8):
    """生成短码（hex 字符串），用于短链 /s/{short_code}"""
    return secrets.token_hex(length // 2)


class InviteCode(models.Model):
    """邀请码：管理员生成，用户扫码后自助注册账号。

    安全策略：有效期 / 使用次数上限 / 注册手机白名单 / 启停控制。
    """
    USER_TYPE_CHOICES = (
        ("internal", "内部用户"),
        ("external", "外部游客"),
    )
    STATUS_CHOICES = (
        (1, "启用"),
        (0, "停用"),
    )

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, verbose_name="所属企业")
    code = models.CharField(max_length=32, unique=True, editable=False, verbose_name="邀请码")
    short_code = models.CharField(max_length=16, unique=True, editable=False, verbose_name="短码")
    remark = models.CharField(max_length=255, null=True, blank=True, verbose_name="备注")
    # 注册手机白名单：非空列表时，注册手机号必须在列表内；空列表不限制
    allowed_phones = CompatibleJSONField(null=True, blank=True, verbose_name="手机白名单")
    user_type = models.CharField(
        max_length=20, choices=USER_TYPE_CHOICES, default="external", verbose_name="注册用户类型"
    )
    max_uses = models.PositiveIntegerField(null=True, blank=True, verbose_name="使用次数上限")
    used_count = models.PositiveIntegerField(default=0, verbose_name="已使用次数")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="有效期至")
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=1, verbose_name="状态")
    # 注册字段覆盖：null 继承租户默认；数组则完全覆盖，元素形如 {"key": "real_name", "required": true}
    fields = CompatibleJSONField(null=True, blank=True, verbose_name="注册字段覆盖")
    # 承载注册页的接入应用：null 表示使用 UAIS 内置注册页
    app = models.ForeignKey(
        "applications.Application", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="invite_codes", verbose_name="承载注册页的接入应用",
    )
    # 码级页面外观覆盖：只存显式配置的项（缺失的项回退租户默认/系统默认），
    # null 表示未配置；合法字段见 invites.appearance.APPEARANCE_KEYS
    appearance = CompatibleJSONField(null=True, blank=True, verbose_name="码级页面外观覆盖")
    # 注册成功后自动加入的用户组 id 列表（应用启用组准入时必填）
    auto_group_ids = CompatibleJSONField(null=True, blank=True, verbose_name="注册后自动加入的用户组")
    created_by = models.CharField(max_length=64, null=True, blank=True, verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invite_code"
        verbose_name = "邀请码"
        ordering = ["-created_at"]

    def __str__(self):
        return f"InviteCode:{self.short_code}"


class ProfileCompletionCode(models.Model):
    """资料补全码：用户扫码后自助补全资料。

    mode=single：绑定具体用户；allow_repeated=False 时提交一次后作废，True 时可反复提交。
    mode=shared：多人通用，扫码后需短信验证身份（本租户绑定该手机号的用户），
                可配置 max_uses 使用上限。
    """
    MODE_CHOICES = (
        ("single", "单人绑定"),
        ("shared", "多人通用"),
    )
    STATUS_CHOICES = (
        (1, "启用"),
        (0, "停用"),
    )

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, verbose_name="所属企业")
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True,
        verbose_name="绑定用户（单人模式）",
    )
    code = models.CharField(max_length=32, unique=True, editable=False, verbose_name="补全码")
    short_code = models.CharField(max_length=16, unique=True, editable=False, verbose_name="短码")
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="single", verbose_name="模式")
    # 允许补全的字段名列表，取值范围见 invites.fields.FIELD_REGISTRY
    fields = CompatibleJSONField(null=True, blank=True, verbose_name="可补全字段")
    allow_repeated = models.BooleanField(default=False, verbose_name="单人模式允许多次提交")
    max_uses = models.PositiveIntegerField(null=True, blank=True, verbose_name="使用次数上限（多人模式）")
    used_count = models.PositiveIntegerField(default=0, verbose_name="已使用次数")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="有效期至")
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=1, verbose_name="状态")
    # 码级页面外观覆盖：结构同 InviteCode.appearance
    appearance = CompatibleJSONField(null=True, blank=True, verbose_name="码级页面外观覆盖")
    created_by = models.CharField(max_length=64, null=True, blank=True, verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profile_completion_code"
        verbose_name = "资料补全码"
        ordering = ["-created_at"]

    def __str__(self):
        return f"CompletionCode:{self.short_code}({self.mode})"
