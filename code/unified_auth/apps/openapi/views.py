from rest_framework.decorators import api_view
from rest_framework.response import Response
from common.response import success, error
from common.errors import ErrorCode
from common.utils import decode_access_token
from apps.accounts.models import User, Department
from apps.accounts.serializers import UserInfoSerializer
from apps.rbac.models import UserRole, RolePermission, Role
from .serializers import (
    VerifyTokenSerializer, CreateUserSerializer, UpdateUserSerializer,
    StatusUpdateSerializer, CheckPermissionSerializer,
)


@api_view(["POST"])
def verify_token(request):
    ser = VerifyTokenSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    payload = decode_access_token(ser.validated_data["token"])
    if payload is None:
        return Response(success({
            "valid": False,
            "user_id": None,
            "tenant_id": None,
            "user_type": None,
        }))

    return Response(success({
        "valid": True,
        "user_id": payload["user_id"],
        "tenant_id": payload["tenant_id"],
        "user_type": payload.get("user_type"),
    }))


@api_view(["GET", "POST"])
def users_view(request):
    if request.method == "GET":
        users = User.objects.filter(tenant_id=request.tenant_id)
        ser = UserInfoSerializer(users, many=True)
        return Response(success({"users": ser.data, "total": users.count()}))

    ser = CreateUserSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    if User.objects.filter(tenant_id=request.tenant_id, username=data["username"]).exists():
        return Response(
            error(ErrorCode.PARAM_INVALID, message="用户名已存在"), status=400
        )

    dept_code = data.get("dept_code")
    dept_id = None
    if dept_code:
        dept = Department.objects.filter(code=dept_code, tenant_id=request.tenant_id).first()
        if not dept:
            return Response(
                error(ErrorCode.PARAM_INVALID, message="指定的部门编码不存在"), status=400
            )
        dept_id = dept.id

    role_codes = data.get("role_codes", [])
    roles = []
    if role_codes:
        roles = list(Role.objects.filter(code__in=role_codes, tenant_id=request.tenant_id))
        if len(roles) != len(role_codes):
            invalid_codes = set(role_codes) - set(r.code for r in roles)
            return Response(
                error(ErrorCode.PARAM_INVALID, message=f"角色编码不存在: {', '.join(invalid_codes)}"), status=400
            )

    user = User.objects.create(
        tenant_id=request.tenant_id,
        user_type=data["user_type"],
        username=data["username"],
        email=data.get("email"),
        phone=data.get("phone"),
        nickname=data.get("nickname"),
        department=data.get("department"),
        dept_id=dept_id,
    )
    user.set_password(data["password"])
    user.save(update_fields=["password"])

    for role in roles:
        UserRole.objects.create(user=user, role=role)

    ser = UserInfoSerializer(user)
    return Response(success(ser.data), status=201)


@api_view(["GET", "PUT"])
def user_detail_view(request, user_id):
    try:
        user = User.objects.get(id=user_id, tenant_id=request.tenant_id)
    except User.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)

    if request.method == "GET":
        ser = UserInfoSerializer(user)
        return Response(success(ser.data))

    ser = UpdateUserSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data

    dept_code = data.get("dept_code")
    if dept_code is not None:
        if dept_code == "":
            user.dept_id = None
        else:
            dept = Department.objects.filter(code=dept_code, tenant_id=request.tenant_id).first()
            if not dept:
                return Response(
                    error(ErrorCode.PARAM_INVALID, message="指定的部门编码不存在"), status=400
                )
            user.dept_id = dept.id

    if "role_codes" in data:
        role_codes = data.get("role_codes") or []
        roles = []
        if role_codes:
            roles = list(Role.objects.filter(code__in=role_codes, tenant_id=request.tenant_id))
            if len(roles) != len(role_codes):
                invalid_codes = set(role_codes) - set(r.code for r in roles)
                return Response(
                    error(ErrorCode.PARAM_INVALID, message=f"角色编码不存在: {', '.join(invalid_codes)}"), status=400
                )
        UserRole.objects.filter(user=user).delete()
        for role in roles:
            UserRole.objects.create(user=user, role=role)

    update_fields = []
    for field in ["nickname", "email", "phone", "avatar", "department"]:
        if field in data and data[field] is not None:
            setattr(user, field, data[field])
            update_fields.append(field)

    if dept_code is not None:
        update_fields.append("dept_id")

    if update_fields:
        user.save(update_fields=update_fields)

    return Response(success({"user_id": user.id}))


@api_view(["PATCH"])
def update_user_status(request, user_id):
    try:
        user = User.objects.get(id=user_id, tenant_id=request.tenant_id)
    except User.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)

    ser = StatusUpdateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    user.status = ser.validated_data["status"]
    user.save(update_fields=["status"])
    return Response(success({"user_id": user.id, "status": user.status}))


@api_view(["POST"])
def check_permission(request):
    ser = CheckPermissionSerializer(data=request.data)
    if not ser.is_valid():
        return Response(error(ErrorCode.PARAM_INVALID, data=ser.errors), status=400)

    data = ser.validated_data
    try:
        user = User.objects.get(id=data["user_id"], tenant_id=request.tenant_id)
    except User.DoesNotExist:
        return Response(error(ErrorCode.USER_NOT_FOUND), status=404)

    has_perm = UserRole.objects.filter(
        user=user,
        role__permissions__code=data["permission_code"],
    ).exists()

    return Response(success({
        "user_id": user.id,
        "permission_code": data["permission_code"],
        "has_permission": has_perm,
    }))
