from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from common.fields import CompatibleJSONField


class Tenant(models.Model):
    name = models.CharField(max_length=128, verbose_name="企业名称")
    slug = models.SlugField(max_length=64, unique=True, verbose_name="唯一标识")
    status = models.BooleanField(default=True, verbose_name="状态")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant"
        verbose_name = "企业租户"

    def __str__(self):
        return self.name


class Department(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, verbose_name="所属企业")
    name = models.CharField(max_length=128, verbose_name="部门名称")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True,
        related_name="children", verbose_name="上级部门",
    )
    sort_order = models.IntegerField(default=0, verbose_name="排序")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "department"
        unique_together = [("tenant", "name")]
        verbose_name = "部门"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, tenant, username, password=None, **extra_fields):
        if not username:
            raise ValueError("用户名不能为空")
        user = self.model(tenant=tenant, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        tenant, _ = Tenant.objects.get_or_create(
            slug="platform",
            defaults={"name": "平台管理"},
        )
        user = self.create_user(tenant, username, password, **extra_fields)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    USER_TYPE_CHOICES = (
        ("internal", "内部用户"),
        ("external", "外部游客"),
    )
    STATUS_CHOICES = (
        (1, "正常"),
        (0, "禁用"),
    )

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, verbose_name="所属企业")
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default="internal")
    username = models.CharField(max_length=64, unique=True, verbose_name="用户名")
    email = models.EmailField(max_length=128, null=True, blank=True, verbose_name="邮箱")
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="手机号")
    nickname = models.CharField(max_length=128, null=True, blank=True, verbose_name="昵称")
    avatar = models.URLField(max_length=512, null=True, blank=True, verbose_name="头像")
    department = models.CharField(max_length=128, null=True, blank=True, verbose_name="部门")
    dept = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="所属部门",
    )
    roles = models.ManyToManyField(
        "rbac.Role", through="rbac.UserRole", related_name="users",
        verbose_name="角色",
    )
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=1, verbose_name="状态")
    last_login_at = models.DateTimeField(null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "user"
        unique_together = [
            ("tenant", "username"),
            ("tenant", "email"),
            ("tenant", "phone"),
        ]
        verbose_name = "用户"

    def __str__(self):
        return f"{self.username}({self.get_user_type_display()})"


class SocialAccount(models.Model):
    PROVIDER_CHOICES = (
        ("wechat_mp", "微信小程序"),
        ("wechat_web", "微信网页"),
        ("dingtalk", "钉钉"),
        ("feishu", "飞书"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="social_accounts")
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    open_id = models.CharField(max_length=128)
    union_id = models.CharField(max_length=128, null=True, blank=True)
    extra_data = CompatibleJSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "social_account"
        unique_together = [("provider", "open_id")]
        verbose_name = "社交账号"

    def __str__(self):
        return f"{self.get_provider_display()}:{self.open_id}"
