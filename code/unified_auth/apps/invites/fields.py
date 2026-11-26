"""资料补全码可配置字段白名单。

model: user 表示存 User 表字段；profile 表示存 UserProfile 表字段。
type: text / date / select（options 供前端渲染下拉框）。
"""

FIELD_REGISTRY = {
    # User 基础字段
    "nickname": {"label": "昵称", "model": "user", "type": "text"},
    "email": {"label": "邮箱", "model": "user", "type": "text"},
    "avatar": {"label": "头像地址", "model": "user", "type": "text"},
    # UserProfile 字段
    "real_name": {"label": "真实姓名", "model": "profile", "type": "text"},
    "gender": {
        "label": "性别", "model": "profile", "type": "select",
        "options": [
            {"value": "male", "label": "男"},
            {"value": "female", "label": "女"},
            {"value": "other", "label": "其他"},
        ],
    },
    "birthday": {"label": "出生日期", "model": "profile", "type": "date"},
    "address": {"label": "联系地址", "model": "profile", "type": "text"},
    "emergency_contact": {"label": "紧急联系人", "model": "profile", "type": "text"},
    "emergency_phone": {"label": "紧急联系电话", "model": "profile", "type": "text"},
    "job_title": {"label": "职位", "model": "profile", "type": "text"},
    "company": {"label": "公司", "model": "profile", "type": "text"},
    "employee_id": {"label": "员工编号", "model": "profile", "type": "text"},
    "work_email": {"label": "工作邮箱", "model": "profile", "type": "text"},
    "work_phone": {"label": "工作电话", "model": "profile", "type": "text"},
    "wechat": {"label": "微信号", "model": "profile", "type": "text"},
    "qq": {"label": "QQ号", "model": "profile", "type": "text"},
    "bio": {"label": "个人简介", "model": "profile", "type": "textarea"},
}
