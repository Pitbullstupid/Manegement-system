"""Giới hạn tần suất gọi API công khai theo IP, đếm trong Redis."""
from __future__ import annotations

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView


class AuthRateThrottle(SimpleRateThrottle):
    """Mức giới hạn lấy từ REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['auth'] (5/min)."""

    scope = "auth"

    def get_cache_key(self, request: Request, view: APIView) -> str:
        # Mỗi endpoint đếm riêng: gọi login nhiều không làm hết lượt của register
        return f"throttle:auth:{view.__class__.__name__}:{self.get_ident(request)}"
