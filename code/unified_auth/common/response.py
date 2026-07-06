import uuid
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from rest_framework.status import HTTP_400_BAD_REQUEST
from common.errors import ErrorCode, ERROR_MESSAGES


def api_response(code=ErrorCode.SUCCESS, data=None, message=None):
    if message is None:
        message = ERROR_MESSAGES.get(code, "unknown")
    body = {
        "code": code,
        "message": message,
        "data": data if data is not None else {},
    }
    if code < 0 and "request_id" not in body.get("data", {}):
        if isinstance(body["data"], dict):
            body["data"]["request_id"] = f"req-{uuid.uuid4().hex[:16]}"
    return body


def success(data=None, message=None):
    return api_response(ErrorCode.SUCCESS, data, message)


def error(code, message=None, data=None):
    return api_response(code, data, message)


def _extract_error_message(detail):
    """从 DRF 错误详情中提取可读的错误消息"""
    if isinstance(detail, dict):
        msgs = []
        for field, errors in detail.items():
            if isinstance(errors, list):
                for e in errors:
                    msgs.append(f"{field}: {str(e)}" if field != "detail" else str(e))
            elif isinstance(errors, str):
                msgs.append(str(errors))
            else:
                msgs.append(str(errors))
        return "; ".join(msgs) if msgs else str(detail)
    if isinstance(detail, list):
        return "; ".join(str(e) for e in detail)
    return str(detail)


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        detail = response.data
        message = _extract_error_message(detail)
        if isinstance(exc, ParseError):
            message = "请求数据格式错误，请检查请求体是否为有效的JSON"
        body = api_response(
            code=ErrorCode.PARAM_INVALID,
            message=message,
        )
        return Response(body, status=response.status_code)
    return response
