import os
import json
import random
import logging

logger = logging.getLogger(__name__)


def generate_code(length=6):
    """生成随机验证码"""
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def send_sms(phone, code, tenant=None):
    """
    发送短信验证码
    优先使用租户自定义的短信配置，未配置则降级到全局环境变量

    Args:
        phone: 手机号码
        code: 验证码
        tenant: 租户对象（可选），用于使用租户自定义的短信渠道

    Returns:
        (success: bool, message: str)
    """
    provider = None
    access_key_id = None
    access_key_secret = None
    sign_name = None
    template_code = None

    if tenant and tenant.sms_provider:
        provider = tenant.sms_provider.lower()
        access_key_id = tenant.sms_access_key_id
        access_key_secret = tenant.sms_access_key_secret
        sign_name = tenant.sms_sign_name
        template_code = tenant.sms_template_code
        logger.info("使用租户短信配置: %s", tenant.name)
    else:
        provider = os.getenv("SMS_PROVIDER", "").lower()
        access_key_id = os.getenv("SMS_ACCESS_KEY_ID")
        access_key_secret = os.getenv("SMS_ACCESS_KEY_SECRET")
        sign_name = os.getenv("SMS_SIGN_NAME")
        template_code = os.getenv("SMS_TEMPLATE_CODE")

    if not provider or provider == "mock":
        logger.info("[DEV] SMS code for %s: %s", phone, code)
        return True, "开发模式（模拟发送）"

    if provider == "aliyun":
        return _send_aliyun(phone, code, access_key_id, access_key_secret, sign_name, template_code)

    logger.warning("未知短信服务商: %s，使用模拟模式", provider)
    logger.info("[DEV] SMS code for %s: %s", phone, code)
    return True, "未知服务商，已降级为模拟发送"


def _send_aliyun(phone, code, access_key_id, access_key_secret, sign_name, template_code):
    """通过阿里云短信服务发送验证码"""
    if not all([access_key_id, access_key_secret, sign_name, template_code]):
        logger.error("阿里云短信配置不完整")
        print(f"[DEV] SMS code for {phone}: {code} (aliyun config incomplete)")
        return False, "短信配置不完整"

    try:
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkdysmsapi.request.v20170525 import SendSmsRequest

        client = AcsClient(access_key_id, access_key_secret, "cn-hangzhou")
        request = SendSmsRequest.SendSmsRequest()
        request.set_PhoneNumbers(phone)
        request.set_SignName(sign_name)
        request.set_TemplateCode(template_code)
        request.set_TemplateParam(json.dumps({"code": code}))

        response = client.do_action_with_exception(request)
        resp_body = json.loads(response.decode("utf-8"))

        if resp_body.get("Code") == "OK":
            logger.info("阿里云短信发送成功: %s -> %s", phone, code)
            print(f"[SMS] 已发送验证码 {code} 到 {phone}")
            return True, "发送成功"
        else:
            logger.error("阿里云短信发送失败: %s", resp_body)
            print(f"[SMS] 阿里云发送失败: {resp_body}")
            print(f"[DEV] SMS code for {phone}: {code}")
            return False, resp_body.get("Message", "发送失败")

    except Exception as e:
        logger.error("阿里云短信发送异常: %s", str(e))
        print(f"[SMS] 阿里云短信异常: {e}")
        print(f"[DEV] SMS code for {phone}: {code}")
        return False, f"短信服务异常: {str(e)}"
