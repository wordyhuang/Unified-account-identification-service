from rest_framework.decorators import api_view
from rest_framework.response import Response
from common.response import success, error
from common.errors import ErrorCode
from apps.audit.models import AuditLog
from .models import UserTag, UserTagBinding


@api_view(["GET"])
def tags_view(request):
    """获取标签列表"""
    qs = UserTag.objects.filter(tenant_id=request.tenant_id, status=True).order_by("sort_order", "created_at")
    return Response(success({
        "tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "color": tag.color,
                "description": tag.description,
                "sort_order": tag.sort_order,
                "created_at": tag.created_at.isoformat() if tag.created_at else None,
            }
            for tag in qs
        ]
    }))


@api_view(["POST"])
def tag_create_view(request):
    """创建标签"""
    name = request.data.get("name", "").strip()
    color = request.data.get("color", "#1890ff")
    description = request.data.get("description")
    description = description.strip() if description is not None else ""

    if not name:
        return Response(error(ErrorCode.PARAM_INVALID, message="标签名称不能为空"), status=400)

    if UserTag.objects.filter(tenant_id=request.tenant_id, name=name).exists():
        return Response(error(ErrorCode.PARAM_INVALID, message="标签名称已存在"), status=400)

    tag = UserTag.objects.create(
        tenant_id=request.tenant_id,
        name=name,
        color=color,
        description=description,
    )

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.tag.create",
        resource_type="user_tag",
        resource_id=tag.id,
        detail={"name": name, "color": color},
    )

    return Response(success({
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
        "description": tag.description,
    }), status=201)


@api_view(["PUT"])
def tag_update_view(request, tag_id):
    """更新标签"""
    try:
        tag = UserTag.objects.get(id=tag_id, tenant_id=request.tenant_id)
    except UserTag.DoesNotExist:
        return Response(error(ErrorCode.PARAM_INVALID, message="标签不存在"), status=404)

    name = request.data.get("name", "").strip()
    color = request.data.get("color")
    description = request.data.get("description")
    description = description.strip() if description is not None else ""

    if name:
        if UserTag.objects.filter(tenant_id=request.tenant_id, name=name).exclude(id=tag_id).exists():
            return Response(error(ErrorCode.PARAM_INVALID, message="标签名称已存在"), status=400)
        tag.name = name

    if color:
        tag.color = color

    tag.description = description
    tag.save(update_fields=["name", "color", "description", "updated_at"])

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.tag.update",
        resource_type="user_tag",
        resource_id=tag.id,
        detail={"name": tag.name, "color": tag.color},
    )

    return Response(success({
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
        "description": tag.description,
    }))


@api_view(["DELETE"])
def tag_delete_view(request, tag_id):
    """删除标签"""
    try:
        tag = UserTag.objects.get(id=tag_id, tenant_id=request.tenant_id)
    except UserTag.DoesNotExist:
        return Response(error(ErrorCode.PARAM_INVALID, message="标签不存在"), status=404)

    tag_name = tag.name
    tag.delete()

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.tag.delete",
        resource_type="user_tag",
        resource_id=tag_id,
        detail={"name": tag_name},
    )

    return Response(success({}))


@api_view(["POST"])
def user_tags_bind_view(request, user_id):
    """给用户添加标签"""
    tag_ids = request.data.get("tag_ids", [])

    if not isinstance(tag_ids, list):
        return Response(error(ErrorCode.PARAM_INVALID, message="tag_ids必须是数组"), status=400)

    valid_tags = UserTag.objects.filter(tenant_id=request.tenant_id, id__in=tag_ids)
    valid_tag_ids = set(valid_tags.values_list("id", flat=True))

    bindings = []
    for tag_id in tag_ids:
        if tag_id in valid_tag_ids:
            binding, created = UserTagBinding.objects.get_or_create(
                user_id=user_id,
                tag_id=tag_id,
            )
            if created:
                bindings.append(binding)

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.user.tags.bind",
        resource_type="user",
        resource_id=user_id,
        detail={"tag_ids": tag_ids},
    )

    return Response(success({
        "count": len(bindings),
        "tag_ids": [b.tag_id for b in bindings],
    }))


@api_view(["DELETE"])
def user_tags_unbind_view(request, user_id):
    """移除用户标签"""
    tag_ids = request.data.get("tag_ids", [])

    if not isinstance(tag_ids, list):
        return Response(error(ErrorCode.PARAM_INVALID, message="tag_ids必须是数组"), status=400)

    deleted_count, _ = UserTagBinding.objects.filter(
        user_id=user_id,
        tag__tenant_id=request.tenant_id,
        tag_id__in=tag_ids,
    ).delete()

    AuditLog.objects.create(
        tenant_id=request.tenant_id,
        actor_id=request.user_id,
        actor_name=request.user.username,
        action="admin.user.tags.unbind",
        resource_type="user",
        resource_id=user_id,
        detail={"tag_ids": tag_ids},
    )

    return Response(success({"deleted_count": deleted_count}))


@api_view(["GET"])
def user_tags_view(request, user_id):
    """获取用户已绑定的标签"""
    bindings = UserTagBinding.objects.filter(user_id=user_id, tag__tenant_id=request.tenant_id)
    return Response(success({
        "tags": [
            {
                "id": b.tag.id,
                "name": b.tag.name,
                "color": b.tag.color,
            }
            for b in bindings
        ]
    }))