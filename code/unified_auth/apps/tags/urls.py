from django.urls import path
from . import views

urlpatterns = [
    path("tags", views.tags_view, name="admin-tags"),
    path("tags/create", views.tag_create_view, name="admin-tag-create"),
    path("tags/<int:tag_id>", views.tag_update_view, name="admin-tag-update"),
    path("tags/<int:tag_id>/delete", views.tag_delete_view, name="admin-tag-delete"),
    path("users/<int:user_id>/tags", views.user_tags_view, name="admin-user-tags"),
    path("users/<int:user_id>/tags/bind", views.user_tags_bind_view, name="admin-user-tags-bind"),
    path("users/<int:user_id>/tags/unbind", views.user_tags_unbind_view, name="admin-user-tags-unbind"),
]