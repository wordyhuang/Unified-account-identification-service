"""码级页面外观解析：邀请码 / 资料补全码共用。

优先级链（字段级回退）：
    码级 appearance（JSON，只存显式配置项） > 租户级默认 > 系统内置默认。

resolve_appearance 必须被公开接口下发、页面渲染、管理端预览三处共用，
与 resolve_invite_fields 保持同模式，避免口径不一致。

安全约束：文本项模板自动转义渲染；图片仅接受 https URL 或 data:image URI；
颜色严格 HEX 6 位校验；不开放自定义 HTML。
"""

import re

# 合法外观字段白名单（码级 appearance 只允许这 7 个键）
APPEARANCE_KEYS = (
    "logo", "title", "welcome", "theme_color",
    "background", "button_text", "footer_text",
)

# 页面类型
PAGE_TYPE_INVITE = "invite"
PAGE_TYPE_COMPLETION = "completion"
PAGE_TYPES = (PAGE_TYPE_INVITE, PAGE_TYPE_COMPLETION)

# 系统内置默认值（租户也未配置时的最终回退；"" 表示由前端保持内置样式）
SYSTEM_DEFAULTS = {
    PAGE_TYPE_INVITE: {
        "logo": "",
        "title": "账号邀请注册",
        "welcome": "",
        "theme_color": "",
        "background": "",
        "button_text": "注册账号",
        "footer_text": "",
    },
    PAGE_TYPE_COMPLETION: {
        "logo": "",
        "title": "资料补全",
        "welcome": "",
        "theme_color": "",
        "background": "",
        "button_text": "提交资料",
        "footer_text": "",
    },
}

HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
IMAGE_URL_PATTERN = re.compile(r"^https://\S+$")
DATA_URI_PATTERN = re.compile(r"^data:image/(png|jpeg|jpg|webp|svg\+xml);base64,[A-Za-z0-9+/=]+$")

# 各文本项长度上限
TEXT_LIMITS = {
    "title": 50,
    "welcome": 100,
    "button_text": 20,
    "footer_text": 100,
}
IMAGE_MAX_LENGTH = 300000  # 约 220KB 图片（data URI base64），与租户级 Logo 上限一致


def _validate_image(value):
    """图片值校验：https URL 或 data:image URI。返回错误消息或 None。"""
    if len(value) > IMAGE_MAX_LENGTH:
        return "图片体积过大（上限约 220KB）"
    if DATA_URI_PATTERN.match(value):
        return None
    if IMAGE_URL_PATTERN.match(value):
        return None
    return "图片仅支持 https 链接或 data URI"


def normalize_appearance(raw):
    """校验并规范化码级外观配置。

    返回 (appearance, error_message)：
    - raw 为 None      → (None, None)，表示清除码级覆盖（存 null）
    - raw 为非 dict    → (None, "错误")
    - raw 为 dict      → 白名单过滤 + 逐项校验；某项值为 ""/None 时删除该项（回退默认）
                         结果为空 dict 时返回 ({}, None)，表示「曾配置但当前全部清空」
    """
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, "外观配置必须为对象"

    out = {}
    for key, value in raw.items():
        if key not in APPEARANCE_KEYS:
            continue  # 非法字段直接丢弃，与 fields 白名单同策略
        if value is None or (isinstance(value, str) and not value.strip()):
            continue  # 空值 = 删除该项（回退默认）
        value = str(value).strip()

        if key == "theme_color":
            if not HEX_COLOR_PATTERN.match(value):
                return None, "appearance.theme_color 颜色格式应为 #RRGGBB"
            out[key] = value
        elif key == "background":
            if HEX_COLOR_PATTERN.match(value) or value.lower().startswith("https://"):
                if HEX_COLOR_PATTERN.match(value):
                    out[key] = value
                else:
                    err = _validate_image(value)
                    if err:
                        return None, f"appearance.background {err}"
                    out[key] = value
            else:
                return None, "appearance.background 仅支持 #RRGGBB 颜色或 https 图片链接"
        elif key in ("logo",):
            err = _validate_image(value)
            if err:
                return None, f"appearance.logo {err}"
            out[key] = value
        else:
            limit = TEXT_LIMITS[key]
            if len(value) > limit:
                return None, f"appearance.{key} 长度不能超过 {limit} 字"
            out[key] = value
    return out, None


def tenant_appearance_defaults(tenant, page_type):
    """租户级默认外观（补全页独立配置 > 邀请品牌字段回退 > 系统内置）。"""
    defaults = dict(SYSTEM_DEFAULTS.get(page_type, SYSTEM_DEFAULTS[PAGE_TYPE_INVITE]))
    if tenant is None:
        return defaults

    # 补全页独立的租户级配置（邀请页不读取）
    completion_cfg = {}
    if page_type == PAGE_TYPE_COMPLETION and isinstance(
        getattr(tenant, "completion_appearance", None), dict
    ):
        completion_cfg = {
            key: value
            for key, value in tenant.completion_appearance.items()
            if key in APPEARANCE_KEYS and value
        }

    # 存量回退：邀请品牌字段对两个页面都生效（补全页保持原有表现）
    if page_type == PAGE_TYPE_INVITE:
        defaults["title"] = tenant.invite_brand_name or tenant.name or defaults["title"]
    elif tenant.invite_brand_name:
        defaults["title"] = tenant.invite_brand_name
    if tenant.invite_welcome:
        defaults["welcome"] = tenant.invite_welcome
    if tenant.invite_theme_color:
        defaults["theme_color"] = tenant.invite_theme_color
    if tenant.invite_logo:
        defaults["logo"] = tenant.invite_logo
    if tenant.invite_background:
        defaults["background"] = tenant.invite_background
    if tenant.invite_submit_text:
        defaults["button_text"] = tenant.invite_submit_text
    if tenant.invite_footer_text:
        defaults["footer_text"] = tenant.invite_footer_text

    # 补全页独立配置逐项覆盖
    for key, value in completion_cfg.items():
        defaults[key] = value
    return defaults


def resolve_appearance(code_obj, tenant, page_type):
    """解析最终生效外观：码级 > 租户级 > 系统内置，字段级回退。

    供公开接口下发、页面渲染、管理端预览三处共用。
    返回包含全部 7 个键的扁平 dict（未配置项为 ""）。
    """
    defaults = tenant_appearance_defaults(tenant, page_type)

    code_cfg = {}
    if code_obj is not None and isinstance(getattr(code_obj, "appearance", None), dict):
        code_cfg = {k: v for k, v in code_obj.appearance.items() if k in APPEARANCE_KEYS}

    result = {}
    for key in APPEARANCE_KEYS:
        value = code_cfg.get(key)
        if value in (None, ""):
            value = defaults.get(key) or ""
        result[key] = value if value not in (None, "") else ""
    return result


def appearance_changed_detail(old, new):
    """对比新旧外观配置，返回审计用变更字段列表，如 ["theme_color:+", "logo:-"]。

    + 新增 / * 修改 / - 清除。
    """
    old = old or {}
    new = new or {}
    changed = []
    for key in APPEARANCE_KEYS:
        old_value = old.get(key)
        new_value = new.get(key)
        if old_value in (None, "") and new_value in (None, ""):
            continue
        if old_value in (None, "") and new_value not in (None, ""):
            changed.append(f"{key}:+")
        elif old_value not in (None, "") and new_value in (None, ""):
            changed.append(f"{key}:-")
        elif old_value != new_value:
            changed.append(f"{key}:*")
    return changed
