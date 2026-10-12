from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from .base import AuthAPITestCase


class TokenTests(AuthAPITestCase):
    def refresh(self, token: str):
        return self.client.post(reverse("token-refresh"), {"refresh": token}, format="json")

    def test_me_requires_token(self) -> None:
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)

    def test_refresh_rotates_and_old_refresh_is_rejected(self) -> None:
        self.create_user()
        tokens = self.login_tokens()
        res = self.refresh(tokens["refresh"])
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)  # refresh mới (xoay vòng)
        self.assertEqual(self.refresh(tokens["refresh"]).status_code, 401)  # refresh cũ đã bị thu hồi

    def test_logout_blacklists_refresh_token(self) -> None:
        user = self.create_user()
        refresh = RefreshToken.for_user(user)
        res = self.post("logout", {"refresh": str(refresh)}, token=str(refresh.access_token))
        self.assertEqual(res.status_code, 204)
        self.assertEqual(self.refresh(str(refresh)).status_code, 401)

    def test_logout_requires_authentication(self) -> None:
        user = self.create_user()
        res = self.post("logout", {"refresh": str(RefreshToken.for_user(user))})
        self.assertEqual(res.status_code, 401)

    def test_logout_with_other_users_refresh_is_rejected(self) -> None:
        a = self.create_user("a@example.com")
        b = self.create_user("b@example.com")
        refresh_a = RefreshToken.for_user(a)
        refresh_b = RefreshToken.for_user(b)
        res = self.post("logout", {"refresh": str(refresh_b)}, token=str(refresh_a.access_token))
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.refresh(str(refresh_b)).status_code, 200)  # token của B còn nguyên
