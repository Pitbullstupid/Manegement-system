"""Lớp nền cho test API xác thực."""
from __future__ import annotations

import re
from typing import Any
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import Role, User
from accounts.throttles import AuthRateThrottle
from common.otp import _key
from common.testing import isolated_settings

PASSWORD = "Matkhau!2026xyz"
EMAIL = "an@example.com"


@isolated_settings
class AuthAPITestCase(APITestCase):
    # Test thường nới rộng để không bị 429; test rate limit sẽ đặt lại "5/min"
    throttle_rate = "1000/min"

    def setUp(self) -> None:
        super().setUp()
        cache.clear()
        patcher = mock.patch.object(
            AuthRateThrottle, "THROTTLE_RATES", {"auth": self.throttle_rate}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def create_user(self, email: str = EMAIL, role: str = Role.EMPLOYEE, **extra: Any) -> User:
        fields: dict[str, Any] = {"is_active": True, "is_email_verified": True}
        fields.update(extra)
        return User.objects.create_user(
            email=email, password=PASSWORD, full_name="Nguyen Van An", role=role, **fields
        )

    def post(self, name: str, data: dict[str, Any], token: str | None = None) -> Response:
        extra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        # on_commit không tự chạy trong TestCase, phải ép chạy thì email mới vào outbox
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse(name), data, format="json", **extra)

    def last_otp(self) -> str:
        match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
        self.assertIsNotNone(match, "Email không chứa mã 6 số")
        return match.group(1)  # type: ignore[union-attr]

    @staticmethod
    def wrong_code(real: str) -> str:
        return "000000" if real != "000000" else "111111"

    def skip_cooldown(self, purpose: str, email: str = EMAIL) -> None:
        cache.delete(_key("otp_cooldown", purpose, email))

    def login_tokens(self, email: str = EMAIL) -> dict[str, str]:
        res = self.post("login", {"email": email, "password": PASSWORD})
        self.assertEqual(res.status_code, 200)
        res = self.post("login-verify", {"email": email, "otp": self.last_otp()})
        self.assertEqual(res.status_code, 200)
        return res.data
