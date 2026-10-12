from django.conf import settings
from django.core import mail
from django.urls import reverse

from common.otp import OTPPurpose

from .base import EMAIL, PASSWORD, AuthAPITestCase


class LoginTests(AuthAPITestCase):
    def test_two_step_login_success(self) -> None:
        self.create_user()
        tokens = self.login_tokens()
        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)
        res = self.client.get(reverse("me"), HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["email"], EMAIL)

    def test_step1_sends_otp_but_no_tokens(self) -> None:
        self.create_user()
        res = self.post("login", {"email": EMAIL, "password": PASSWORD})
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("access", res.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [EMAIL])
        self.assertEqual(mail.outbox[0].subject, "Mã xác thực đăng nhập")

    def test_unknown_email_and_wrong_password_look_identical(self) -> None:
        self.create_user()
        wrong_pw = self.post("login", {"email": EMAIL, "password": "saimatkhau"})
        unknown = self.post("login", {"email": "khongco@example.com", "password": "saimatkhau"})
        self.assertEqual(wrong_pw.status_code, 401)
        self.assertEqual(unknown.status_code, 401)
        self.assertEqual(wrong_pw.data, unknown.data)
        self.assertEqual(len(mail.outbox), 0)

    def test_inactive_or_unverified_user_cannot_login(self) -> None:
        self.create_user("chuakichhoat@example.com", is_active=False, is_email_verified=False)
        self.create_user("bikhoa@example.com", is_active=False, is_email_verified=True)
        for email in ("chuakichhoat@example.com", "bikhoa@example.com"):
            with self.subTest(email=email):
                res = self.post("login", {"email": email, "password": PASSWORD})
                self.assertEqual(res.status_code, 401)
        self.assertEqual(len(mail.outbox), 0)

    def test_step2_without_step1_rejected(self) -> None:
        self.create_user()
        res = self.post("login-verify", {"email": EMAIL, "otp": "123456"})
        self.assertEqual(res.status_code, 400)
        self.assertNotIn("access", res.data)

    def test_wrong_login_otp_rejected(self) -> None:
        self.create_user()
        self.post("login", {"email": EMAIL, "password": PASSWORD})
        wrong = self.wrong_code(self.last_otp())
        res = self.post("login-verify", {"email": EMAIL, "otp": wrong})
        self.assertEqual(res.status_code, 400)
        self.assertNotIn("access", res.data)

    def test_login_otp_cannot_be_reused(self) -> None:
        self.create_user()
        self.post("login", {"email": EMAIL, "password": PASSWORD})
        code = self.last_otp()
        self.assertEqual(self.post("login-verify", {"email": EMAIL, "otp": code}).status_code, 200)
        self.assertEqual(self.post("login-verify", {"email": EMAIL, "otp": code}).status_code, 400)

    def test_login_otp_locked_after_max_wrong_attempts(self) -> None:
        self.create_user()
        self.post("login", {"email": EMAIL, "password": PASSWORD})
        code = self.last_otp()
        for _ in range(settings.OTP_MAX_ATTEMPTS):
            res = self.post("login-verify", {"email": EMAIL, "otp": self.wrong_code(code)})
            self.assertEqual(res.status_code, 400)
        res = self.post("login-verify", {"email": EMAIL, "otp": code})
        self.assertEqual(res.status_code, 400)
        self.assertNotIn("access", res.data)

    def test_resend_login_before_step1_sends_nothing_and_does_not_block_login(self) -> None:
        self.create_user()
        res = self.post("resend-otp", {"email": EMAIL, "purpose": "LOGIN"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        # Kẻ lạ gọi resend không được làm người thật bị cooldown khi đăng nhập
        res = self.post("login", {"email": EMAIL, "password": PASSWORD})
        self.assertEqual(res.status_code, 200)

    def test_resend_login_after_step1_sends_new_working_code(self) -> None:
        self.create_user()
        self.post("login", {"email": EMAIL, "password": PASSWORD})
        self.skip_cooldown(OTPPurpose.LOGIN)
        res = self.post("resend-otp", {"email": EMAIL, "purpose": "LOGIN"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
        res = self.post("login-verify", {"email": EMAIL, "otp": self.last_otp()})
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)

    def test_resend_for_unknown_email_gives_same_answer_and_sends_nothing(self) -> None:
        res = self.post("resend-otp", {"email": "khongco@example.com", "purpose": "REGISTER"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
