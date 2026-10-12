import time
from unittest import mock

from django.conf import settings
from django.core import mail

from accounts.models import User
from common.otp import OTPPurpose

from .base import EMAIL, PASSWORD, AuthAPITestCase

REGISTER_DATA = {"email": EMAIL, "password": PASSWORD, "full_name": "Nguyen Van An"}


class RegisterVerifyTests(AuthAPITestCase):
    def register(self) -> str:
        res = self.post("register", REGISTER_DATA)
        self.assertEqual(res.status_code, 201)
        return self.last_otp()

    def verify(self, code: str):
        return self.post("verify-email", {"email": EMAIL, "otp": code})

    def test_register_creates_inactive_user_and_sends_vietnamese_email(self) -> None:
        code = self.register()
        user = User.objects.get(email=EMAIL)
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_email_verified)
        self.assertNotEqual(user.password, PASSWORD)  # mật khẩu đã được băm
        self.assertTrue(user.check_password(PASSWORD))

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, [EMAIL])
        self.assertEqual(msg.subject, "Mã xác thực đăng ký tài khoản")
        self.assertIn(code, msg.body)
        self.assertIn(f"{settings.OTP_TTL_SECONDS // 60} phút", msg.body)
        html, mimetype = msg.alternatives[0]  # bản HTML đi kèm bản text
        self.assertEqual(mimetype, "text/html")
        self.assertIn(code, html)

    def test_correct_otp_activates_account(self) -> None:
        code = self.register()
        self.assertEqual(self.verify(code).status_code, 200)
        user = User.objects.get(email=EMAIL)
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)

    def test_wrong_otp_rejected(self) -> None:
        code = self.register()
        res = self.verify(self.wrong_code(code))
        self.assertEqual(res.status_code, 400)
        self.assertFalse(User.objects.get(email=EMAIL).is_active)

    def test_expired_otp_rejected(self) -> None:
        code = self.register()
        future = time.time() + settings.OTP_TTL_SECONDS + 1
        with mock.patch("time.time", return_value=future):
            res = self.verify(code)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(User.objects.get(email=EMAIL).is_active)

    def test_used_otp_cannot_be_reused(self) -> None:
        code = self.register()
        self.assertEqual(self.verify(code).status_code, 200)
        self.assertEqual(self.verify(code).status_code, 400)

    def test_more_than_max_wrong_attempts_locks_code(self) -> None:
        code = self.register()
        for _ in range(settings.OTP_MAX_ATTEMPTS):
            self.assertEqual(self.verify(self.wrong_code(code)).status_code, 400)
        res = self.verify(code)  # đúng mã nhưng đã sai quá số lần
        self.assertEqual(res.status_code, 400)
        self.assertIn("quá nhiều", res.data["detail"])
        self.assertEqual(self.verify(code).status_code, 400)  # mã đã bị hủy
        self.assertFalse(User.objects.get(email=EMAIL).is_active)

    def test_resend_within_cooldown_rejected(self) -> None:
        self.register()
        res = self.post("resend-otp", {"email": EMAIL, "purpose": "REGISTER"})
        self.assertEqual(res.status_code, 429)
        self.assertGreater(int(res["Retry-After"]), 0)
        self.assertEqual(len(mail.outbox), 1)  # không gửi thêm mail

    def test_resend_after_cooldown_issues_new_working_code(self) -> None:
        self.register()
        self.skip_cooldown(OTPPurpose.REGISTER)
        res = self.post("resend-otp", {"email": EMAIL, "purpose": "REGISTER"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(self.verify(self.last_otp()).status_code, 200)

    def test_register_with_verified_email_rejected(self) -> None:
        self.create_user()
        res = self.post("register", REGISTER_DATA)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_reregister_unverified_updates_name_and_password(self) -> None:
        self.register()
        self.skip_cooldown(OTPPurpose.REGISTER)
        new = {"email": EMAIL, "password": "Matkhau!Moi2026", "full_name": "Ten Moi"}
        self.assertEqual(self.post("register", new).status_code, 201)
        user = User.objects.get(email=EMAIL)
        self.assertEqual(user.full_name, "Ten Moi")
        self.assertTrue(user.check_password("Matkhau!Moi2026"))
        self.assertEqual(len(mail.outbox), 2)

    def test_weak_password_rejected(self) -> None:
        res = self.post("register", {**REGISTER_DATA, "password": "12345678"})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(User.objects.filter(email=EMAIL).exists())
