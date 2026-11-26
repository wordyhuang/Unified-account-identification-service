"""应用准入判定（单一事实来源）。

判定链（详见 document/用户组与应用准入控制方案_v1.0.md 第 5 章）：

1. 开放应用（default_access_user_types 含 external）：组不参与，
   沿用 UserAppAccess 显式授权 OR 用户类型匹配。
2. 内部应用且已绑定组：必须是 internal 用户且属于任一绑定组（组为唯一依据）。
3. 内部应用未绑定组：完全沿用原有逻辑，保证存量行为不变。

本函数供 Token 中间件、OAuth2 授权确认页、管理端准入诊断共用，
任何准入规则调整都必须改这里，避免多处实现漂移。
"""

from .models import AppGroupBinding, UserGroupMember, UserAppAccess

# 判定原因码：用于管理端准入诊断回显，不对外暴露敏感信息
REASON_OPEN_EXPLICIT = "open_app_explicit"          # 开放应用：显式授权放行
REASON_OPEN_TYPE_MATCH = "open_app_type_match"      # 开放应用：用户类型匹配放行
REASON_OPEN_DENIED = "open_app_denied"              # 开放应用：拒绝
REASON_GROUP_MATCHED = "group_mode_matched"         # 组模式：命中绑定组放行
REASON_GROUP_DENIED = "group_mode_denied"           # 组模式：未命中绑定组
REASON_GROUP_EXTERNAL_DENIED = "group_mode_external_denied"  # 组模式：非内部用户
REASON_LEGACY_TYPE_MATCH = "legacy_type_match"      # 未绑组：用户类型匹配放行
REASON_LEGACY_EXPLICIT = "legacy_explicit"          # 未绑组：显式授权放行
REASON_LEGACY_DENIED = "legacy_denied"              # 未绑组：拒绝
REASON_TENANT_MISMATCH = "tenant_mismatch"          # 用户与应用不同租户


def is_open_app(app):
    """勾选外部用户（开放用户）的应用为开放应用，用户组不生效。"""
    return "external" in (app.default_access_user_types or [])


def has_group_binding(app):
    """应用是否已绑定准入组（含已停用的组，停用组不放行但保持组模式生效）。"""
    return AppGroupBinding.objects.filter(
        app_id=app.id, group__tenant_id=app.tenant_id,
    ).exists()


def is_group_mode(app):
    """应用是否处于组准入模式：内部应用且已绑定组。"""
    return (not is_open_app(app)) and has_group_binding(app)


def matched_group(user, app):
    """返回用户命中的绑定组（同租户、启用），未命中返回 None。"""
    if user.tenant_id != app.tenant_id:
        return None
    return (
        UserGroupMember.objects.filter(
            user=user,
            group__app_bindings__app_id=app.id,
            group__tenant_id=user.tenant_id,
            group__status=True,
        )
        .select_related("group")
        .first()
    )


def _explicit_access(user, app):
    return UserAppAccess.objects.filter(
        user=user, app_id=app.id, status="active",
    ).exists()


def evaluate_app_access(user, app):
    """返回 (allowed: bool, reason: str, matched_group_id: int|None)。

    调用方：token 中间件、OAuth2 授权确认页、管理端准入诊断。
    """
    types = app.default_access_user_types or []

    # 0. 租户边界：跨租户一律拒绝（令牌中的 app_id 与用户租户必须一致）
    if user.tenant_id != app.tenant_id:
        return False, REASON_TENANT_MISMATCH, None

    # 1. 开放应用：用户组不参与
    if "external" in types:
        if _explicit_access(user, app):
            return True, REASON_OPEN_EXPLICIT, None
        if user.user_type in types:
            return True, REASON_OPEN_TYPE_MATCH, None
        return False, REASON_OPEN_DENIED, None

    # 2/3. 内部应用：先判断是否绑组，避免未绑组时多查一次成员关系
    if not has_group_binding(app):
        if _explicit_access(user, app):
            return True, REASON_LEGACY_EXPLICIT, None
        if user.user_type in types:
            return True, REASON_LEGACY_TYPE_MATCH, None
        return False, REASON_LEGACY_DENIED, None

    if user.user_type != "internal":
        return False, REASON_GROUP_EXTERNAL_DENIED, None

    group_member = matched_group(user, app)
    if group_member is not None:
        return True, REASON_GROUP_MATCHED, group_member.group_id
    return False, REASON_GROUP_DENIED, None
