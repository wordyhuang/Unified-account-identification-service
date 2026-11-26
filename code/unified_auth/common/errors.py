class ErrorCode:
    SUCCESS = 0

    TOKEN_EXPIRED = -10001
    TOKEN_INVALID = -10002
    SIGNATURE_INVALID = -10003

    USER_NOT_FOUND = -10101
    USER_DISABLED = -10102
    USER_ACCESS_DENIED = -10103
    PASSWORD_CHANGE_REQUIRED = -10104
    PASSWORD_ERROR = -10105

    PERMISSION_DENIED = -10201
    NO_API_PERMISSION = -10202

    TENANT_NOT_FOUND = -10203
    TENANT_SELECT_REQUIRED = -10204

    SMS_CODE_INVALID = -10301
    SMS_CODE_EXPIRED = -10302
    SMS_SEND_FAILED = -10303

    RATE_LIMIT_EXCEEDED = -10401

    APP_KEY_INVALID = -10501
    APP_DISABLED = -10502

    PARAM_MISSING = -10601
    PARAM_INVALID = -10602

    INVITE_CODE_INVALID = -10701
    INVITE_CODE_EXPIRED = -10702
    INVITE_CODE_EXHAUSTED = -10703
    INVITE_PHONE_NOT_ALLOWED = -10704
    COMPLETION_SESSION_INVALID = -10705

    WECHAT_NOT_CONFIGURED = -10801
    WECHAT_API_ERROR = -10802

    INTERNAL_ERROR = -10901


ERROR_MESSAGES = {
    ErrorCode.SUCCESS: "success",
    ErrorCode.TOKEN_EXPIRED: "Token 已过期",
    ErrorCode.TOKEN_INVALID: "Token 无效",
    ErrorCode.SIGNATURE_INVALID: "签名无效",
    ErrorCode.USER_NOT_FOUND: "用户不存在",
    ErrorCode.USER_DISABLED: "用户已被禁用",
    ErrorCode.USER_ACCESS_DENIED: "无权访问此系统",
    ErrorCode.PERMISSION_DENIED: "权限不足",
    ErrorCode.NO_API_PERMISSION: "无接口调用权限",
    ErrorCode.TENANT_NOT_FOUND: "租户不存在，请联系管理员",
    ErrorCode.TENANT_SELECT_REQUIRED: "该用户名在多个租户中存在，请选择租户后登录",
    ErrorCode.SMS_CODE_INVALID: "验证码错误",
    ErrorCode.SMS_CODE_EXPIRED: "验证码已过期，请重新获取",
    ErrorCode.SMS_SEND_FAILED: "短信发送失败",
    ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁，请稍后再试",
    ErrorCode.APP_KEY_INVALID: "AppKey 无效",
    ErrorCode.APP_DISABLED: "应用已被禁用",
    ErrorCode.PARAM_MISSING: "缺少必要参数",
    ErrorCode.PARAM_INVALID: "参数格式错误",
    ErrorCode.PASSWORD_CHANGE_REQUIRED: "密码已被管理员重置，请先修改密码",
    ErrorCode.PASSWORD_ERROR: "用户名或密码错误",
    ErrorCode.INVITE_CODE_INVALID: "邀请码无效或已停用",
    ErrorCode.INVITE_CODE_EXPIRED: "邀请码已过期",
    ErrorCode.INVITE_CODE_EXHAUSTED: "邀请码使用次数已达上限",
    ErrorCode.INVITE_PHONE_NOT_ALLOWED: "手机号不在邀请白名单内",
    ErrorCode.COMPLETION_SESSION_INVALID: "补全会话无效或已过期，请重新验证",
    ErrorCode.WECHAT_NOT_CONFIGURED: "微信应用未配置，请联系管理员",
    ErrorCode.WECHAT_API_ERROR: "微信API调用失败",
    ErrorCode.INTERNAL_ERROR: "服务内部错误",
}
