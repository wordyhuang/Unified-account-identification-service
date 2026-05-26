import uuid
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
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


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        detail = response.data
        body = api_response(
            code=ErrorCode.PARAM_INVALID,
            message=str(detail),
            data={"detail": detail},
        )
        return Response(body, status=response.status_code)
    return response
