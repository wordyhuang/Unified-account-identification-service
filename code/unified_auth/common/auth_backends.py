"""多租户认证后端。

username 仅租户内唯一，不同租户允许重复用户名/手机号。
默认的 ModelBackend 按 username 全局查询，同名用户会抛 MultipleObjectsReturned，
这里改为：可传入 tenant_id 限定租户；不传时若命中多个同名用户则返回 None（登录失败），避免崩溃。
"""
from django.contrib.auth.backends import ModelBackend

from apps.accounts.models import User


class TenantModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, tenant_id=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            qs = User._default_manager.all()
            if tenant_id is not None:
                qs = qs.filter(tenant_id=tenant_id)
            user = qs.get(username=username)
        except User.DoesNotExist:
            User().set_password(password)
        except User.MultipleObjectsReturned:
            # 未指定租户时命中多个同名用户，无法确定身份
            return None
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
