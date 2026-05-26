import os
import json
import random
import logging

logger = logging.getLogger(__name__)


def generate_code(length=6):
    """生成随机验证码"""
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def send_sms(phone, code):
    """
    发送短信验证码
    
    Args:
        phone: 手机号码
        code: 验证码
    
    Returns:
        (success: bool, message: str)
    """
    provider = os.getenv("SMS_PROVIDER", "").lower()

    if not provider or provider == "mock":
        logger.info("[DEV] SMS code for %s: %s", phone, code)
        return True, "开发模式（模拟发送）"

    if provider == "aliyun":
        return _send_aliyun(phone, code)

    logger.warning("未知短信服务商: %s，使用模拟模式", provider)
    logger.info("[DEV] SMS code for %s: %s", phone, code)
    return True, "未知服务商，已降级为模拟发送"


def _send_aliyun(phone, code):
    """通过阿里云短信服务发送验证码"""
    access_key_id = os.getenv("SMS_ACCESS_KEY_ID")
    access_key_secret = os.getenv("SMS_ACCESS_KEY_SECRET")
    sign_name = os.getenv("SMS_SIGN_NAME")
    template_code = os.getenv("SMS_TEMPLATE_CODE")

    if not all([access_key_id, access_key_secret, sign_name, template_code]):
        logger.error("阿里云短信配置不完整，请检查环境变量")
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
