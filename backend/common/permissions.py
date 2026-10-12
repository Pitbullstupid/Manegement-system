"""Permission classes theo vai trò (RBAC). Luôn kiểm tra ở backend, frontend chỉ ẩn/hiện UI."""
from __future__ import annotations

from typing import Any

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from accounts.models import Role


class IsAdmin(BasePermission):
    message = "Chỉ quản trị viên mới có quyền thực hiện thao tác này."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.ADMIN)


class IsManagerOrAdmin(BasePermission):
    message = "Chỉ quản lý hoặc quản trị viên mới có quyền thực hiện thao tác này."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(
            user and user.is_authenticated and user.role in (Role.MANAGER, Role.ADMIN)
        )


class IsOwnerOrReadOnly(BasePermission):
    """Ai cũng được xem (GET/HEAD/OPTIONS), chỉ chủ sở hữu mới được sửa/xóa.

    Mặc định chủ sở hữu là `obj.owner`. View có thể đổi bằng thuộc tính `owner_field`,
    ví dụ `owner_field = "created_by"`.
    """

    message = "Bạn chỉ được chỉnh sửa dữ liệu do chính mình tạo."

    def has_object_permission(self, request: Request, view: APIView, obj: Any) -> bool:
        if request.method in SAFE_METHODS:
            return True
        owner = getattr(obj, getattr(view, "owner_field", "owner"), None)
        return owner is not None and owner == request.user
