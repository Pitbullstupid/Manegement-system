import time
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase

from common.otp import (
    OTPCooldownError,
    OTPPurpose,
    OTPTooManyAttemptsError,
    _key,
    issue_otp,
    verify_otp,
)
from common.testing import isolated_settings

EMAIL = "otp@example.com"
P = OTPPurpose.LOGIN


def _wrong(code: str) -> str:
    return "000000" if code != "000000" else "111111"


@isolated_settings
class OTPTests(SimpleTestCase):
    def setUp(self) -> None:
        cache.clear()

    def test_code_is_six_digits(self) -> None:
        self.assertRegex(issue_otp(P, EMAIL), r"^\d{6}$")

    def test_stored_value_is_hash_not_plain_code(self) -> None:
        code = issue_otp(P, EMAIL)
        stored = cache.get(_key("otp", P, EMAIL))
        self.assertNotEqual(stored, code)
        self.assertEqual(len(stored), 64)  # SHA-256 dạng hex

    def test_correct_code_is_single_use(self) -> None:
        code = issue_otp(P, EMAIL)
        self.assertTrue(verify_otp(P, EMAIL, code))
        self.assertFalse(verify_otp(P, EMAIL, code))

    def test_wrong_code_rejected_but_correct_code_still_works(self) -> None:
        code = issue_otp(P, EMAIL)
        self.assertFalse(verify_otp(P, EMAIL, _wrong(code)))
        self.assertTrue(verify_otp(P, EMAIL, code))

    def test_too_many_wrong_attempts_discards_code(self) -> None:
        code = issue_otp(P, EMAIL)
        for _ in range(settings.OTP_MAX_ATTEMPTS):
            self.assertFalse(verify_otp(P, EMAIL, _wrong(code)))
        with self.assertRaises(OTPTooManyAttemptsError):
            verify_otp(P, EMAIL, code)  # đúng mã nhưng đã vượt số lần cho phép
        self.assertFalse(verify_otp(P, EMAIL, code))  # mã đã bị hủy

    def test_resend_within_cooldown_rejected(self) -> None:
        issue_otp(P, EMAIL)
        with self.assertRaises(OTPCooldownError) as ctx:
            issue_otp(P, EMAIL)
        self.assertGreater(ctx.exception.retry_after, 0)
        self.assertLessEqual(ctx.exception.retry_after, settings.OTP_RESEND_COOLDOWN)

    def test_expired_code_rejected(self) -> None:
        code = issue_otp(P, EMAIL)
        future = time.time() + settings.OTP_TTL_SECONDS + 1
        with mock.patch("time.time", return_value=future):
            self.assertFalse(verify_otp(P, EMAIL, code))

    def test_code_for_one_purpose_does_not_work_for_another(self) -> None:
        code = issue_otp(OTPPurpose.REGISTER, EMAIL)
        self.assertFalse(verify_otp(OTPPurpose.LOGIN, EMAIL, code))

    def test_email_is_case_insensitive(self) -> None:
        code = issue_otp(P, "Otp@Example.COM")
        self.assertTrue(verify_otp(P, "otp@example.com", code))
