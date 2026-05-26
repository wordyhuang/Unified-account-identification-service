class ErrorCode:
    SUCCESS = 0

    TOKEN_EXPIRED = -10001
    TOKEN_INVALID = -10002
    SIGNATURE_INVALID = -10003

    USER_NOT_FOUND = -10101
    USER_DISABLED = -10102
    USER_ACCESS_DENIED = -10103

    PERMISSION_DENIED = -10201
    NO_API_PERMISSION = -10202

    SMS_CODE_INVALID = -10301
    SMS_CODE_EXPIRED = -10302
    SMS_SEND_FAILED = -10303

    RATE_LIMIT_EXCEEDED = -10401

    APP_KEY_INVALID = -10501
    APP_DISABLED = -10502

    PARAM_MISSING = -10601
    PARAM_INVALID = -10602


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
    ErrorCode.SMS_CODE_INVALID: "验证码错误",
    ErrorCode.SMS_CODE_EXPIRED: "验证码已过期，请重新获取",
    ErrorCode.SMS_SEND_FAILED: "短信发送失败",
    ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁，请稍后再试",
    ErrorCode.APP_KEY_INVALID: "AppKey 无效",
    ErrorCode.APP_DISABLED: "应用已被禁用",
    ErrorCode.PARAM_MISSING: "缺少必要参数",
    ErrorCode.PARAM_INVALID: "参数格式错误",
}
