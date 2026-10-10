from django.conf import settings
from django.db import connection
from django_redis import get_redis_connection
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response


def _check_database() -> dict:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")  # Câu truy vấn rẻ nhất để thử kết nối
            cursor.fetchone()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        # Chỉ lộ chi tiết lỗi khi DEBUG, tránh rò thông tin ở production
        return {"status": "error", **({"detail": str(exc)} if settings.DEBUG else {})}


def _check_redis() -> dict:
    try:
        get_redis_connection("default").ping()  # Gửi PING thật tới Redis
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", **({"detail": str(exc)} if settings.DEBUG else {})}


@api_view(["GET"])
@authentication_classes([])      # Health check công khai, không cần đăng nhập
@permission_classes([AllowAny])
def health_check(request: Request) -> Response:
    services = {"database": _check_database(), "redis": _check_redis()}
    healthy = all(s["status"] == "ok" for s in services.values())
    return Response(
        {"status": "ok" if healthy else "error", "services": services},
        # 503 để monitoring nhận ra hệ thống đang có vấn đề
        status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
