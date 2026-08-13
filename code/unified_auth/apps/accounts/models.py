import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from common.fields import CompatibleJSONField


class Tenant(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, verbose_name="UUID")
    name = models.CharField(max_length=128, verbose_name="企业名称")
    slug = models.SlugField(max_length=64, unique=True, verbose_name="唯一标识")
    status = models.BooleanField(default=True, verbose_name="状态")

    # 自定义短信渠道配置
    sms_provider = models.CharField(max_length=32, null=True, blank=True, verbose_name="短信服务商")
    sms_access_key_id = models.CharField(max_length=256, null=True, blank=True, verbose_name="短信AccessKey")
    sms_access_key_secret = models.CharField(max_length=512, null=True, blank=True, verbose_name="短信AccessSecret")
    sms_sign_name = models.CharField(max_length=64, null=True, blank=True, verbose_name="短信签名")
    sms_template_code = models.CharField(max_length=64, null=True, blank=True, verbose_name="短信模板编码")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant"
        verbose_name = "企业租户"

    def __str__(self):
        return self.name


class Department(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, verbose_name="UUID")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, verbose_name="所属企业")
    name = models.CharField(max_length=128, verbose_name="部门名称")
    code = models.CharField(max_length=64, null=True, blank=True, verbose_name="部门编码")
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
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, verbose_name="UUID")
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
    # 用户名仅租户内唯一（unique_together 见 Meta），不同租户允许重复用户名/手机号
    username = models.CharField(max_length=64, verbose_name="用户名")
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


class UserProfile(models.Model):
    GENDER_CHOICES = (
        ("male", "男"),
        ("female", "女"),
        ("other", "其他"),
    )

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile", verbose_name="关联用户"
    )

    # 基本信息
    avatar = models.URLField(max_length=512, null=True, blank=True, verbose_name="头像")
    real_name = models.CharField(max_length=64, null=True, blank=True, verbose_name="真实姓名")
    gender = models.CharField(
        max_length=10, choices=GENDER_CHOICES, null=True, blank=True, verbose_name="性别"
    )
    birthday = models.DateField(null=True, blank=True, verbose_name="出生日期")
    id_card = models.CharField(max_length=32, null=True, blank=True, verbose_name="身份证号")
    nationality = models.CharField(max_length=64, null=True, blank=True, verbose_name="国籍")

    # 联系信息
    address = models.CharField(max_length=512, null=True, blank=True, verbose_name="联系地址")
    zip_code = models.CharField(max_length=20, null=True, blank=True, verbose_name="邮政编码")
    emergency_contact = models.CharField(max_length=64, null=True, blank=True, verbose_name="紧急联系人")
    emergency_phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="紧急联系电话")

    # 工作信息
    job_title = models.CharField(max_length=128, null=True, blank=True, verbose_name="职位")
    company = models.CharField(max_length=256, null=True, blank=True, verbose_name="公司")
    employee_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="员工编号")
    hire_date = models.DateField(null=True, blank=True, verbose_name="入职日期")
    work_email = models.EmailField(max_length=128, null=True, blank=True, verbose_name="工作邮箱")
    work_phone = models.CharField(max_length=32, null=True, blank=True, verbose_name="工作电话")

    # 社交信息
    wechat = models.CharField(max_length=64, null=True, blank=True, verbose_name="微信号")
    qq = models.CharField(max_length=32, null=True, blank=True, verbose_name="QQ号")
    weibo = models.CharField(max_length=128, null=True, blank=True, verbose_name="微博账号")

    # 扩展信息
    bio = models.TextField(null=True, blank=True, verbose_name="个人简介")
    interests = models.CharField(max_length=512, null=True, blank=True, verbose_name="兴趣爱好")
    tags = CompatibleJSONField(null=True, blank=True, verbose_name="标签")
    extra_data = CompatibleJSONField(null=True, blank=True, verbose_name="扩展数据")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_profile"
        verbose_name = "用户资料"

    def __str__(self):
        return f"Profile of {self.user.username}"
