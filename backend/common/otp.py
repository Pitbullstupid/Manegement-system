"""Sinh, lưu, kiểm tra OTP 6 số bằng Redis (qua Django cache API).

Quy tắc:
- Mã sinh bằng `secrets`, KHÔNG lưu mã gốc, chỉ lưu bản băm HMAC.
- Mỗi mã sống OTP_TTL_SECONDS, sai tối đa OTP_MAX_ATTEMPTS lần.
- Giữa 2 lần gửi phải cách nhau OTP_RESEND_COOLDOWN giây.
- Dùng một lần: đúng là xóa ngay.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from django.conf import settings
from django.core.cache import cache
from django.db import models


class OTPPurpose(models.TextChoices):
    REGISTER = "REGISTER", "Đăng ký"
    LOGIN = "LOGIN", "Đăng nhập"


class OTPError(Exception):
    """Lớp cha cho mọi lỗi OTP."""


class OTPCooldownError(OTPError):
    """Gửi lại quá nhanh. `retry_after` là số giây còn phải chờ."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Vui lòng chờ {retry_after} giây trước khi gửi lại mã.")
        self.retry_after = retry_after


class OTPTooManyAttemptsError(OTPError):
    """Nhập sai quá số lần cho phép, mã đã bị hủy."""


def _normalize(email: str) -> str:
    return email.strip().lower()


def _key(kind: str, purpose: str, email: str) -> str:
    # Ví dụ: otp:LOGIN:a@x.com | otp_attempts:LOGIN:a@x.com | otp_cooldown:...
    return f"{kind}:{purpose}:{_normalize(email)}"


def _hash_code(purpose: str, email: str, code: str) -> str:
    """HMAC-SHA256, khóa là SECRET_KEY. Gắn purpose + email để mã không dùng chéo được."""
    message = f"{purpose}:{_normalize(email)}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _generate_code() -> str:
    # randbelow(10**6) cho 0..999999, zfill đệm số 0 đầu: 7341 -> "007341"
    return str(secrets.randbelow(10**6)).zfill(6)


def _remaining_cooldown(key: str) -> int:
    """Số giây còn lại của cooldown. Cache không hỗ trợ ttl thì trả toàn bộ cooldown."""
    ttl_func = getattr(cache, "ttl", None)
    ttl = ttl_func(key) if ttl_func else None
    if ttl is None or ttl <= 0:
        return settings.OTP_RESEND_COOLDOWN
    return int(ttl)


def issue_otp(purpose: str, email: str) -> str:
    """Tạo mã mới, lưu bản băm, trả mã gốc để gửi email.

    Raises:
        OTPCooldownError: nếu vừa gửi mã cách đây chưa đủ cooldown.
    """
    cooldown_key = _key("otp_cooldown", purpose, email)
    # add() chỉ ghi khi key chưa có, và Redis làm nguyên tử -> chặn được request song song
    if not cache.add(cooldown_key, 1, timeout=settings.OTP_RESEND_COOLDOWN):
        raise OTPCooldownError(_remaining_cooldown(cooldown_key))

    code = _generate_code()
    ttl = settings.OTP_TTL_SECONDS
    cache.set(_key("otp", purpose, email), _hash_code(purpose, email, code), timeout=ttl)
    cache.set(_key("otp_attempts", purpose, email), 0, timeout=ttl)  # mã mới thì đếm lại từ 0
    return code


def _discard(purpose: str, email: str) -> None:
    cache.delete_many(
        [_key("otp", purpose, email), _key("otp_attempts", purpose, email)]
    )


def verify_otp(purpose: str, email: str, code: str) -> bool:
    """Kiểm tra mã. Đúng thì xóa mã (dùng một lần) và trả True.

    Mã sai, hết hạn hay chưa từng gửi đều trả False (không phân biệt).

    Raises:
        OTPTooManyAttemptsError: nếu đã sai quá OTP_MAX_ATTEMPTS lần.
    """
    code_key = _key("otp", purpose, email)
    attempts_key = _key("otp_attempts", purpose, email)

    stored_hash = cache.get(code_key)
    if stored_hash is None:
        return False  # hết hạn, đã dùng, hoặc chưa từng gửi

    try:
        attempts = cache.incr(attempts_key)  # tăng nguyên tử
    except ValueError:  # key đếm đã hết hạn trước: coi như lần đầu
        cache.set(attempts_key, 1, timeout=settings.OTP_TTL_SECONDS)
        attempts = 1

    if attempts > settings.OTP_MAX_ATTEMPTS:
        _discard(purpose, email)
        raise OTPTooManyAttemptsError("Nhập sai quá nhiều lần, vui lòng gửi mã mới.")

    # compare_digest so sánh trong thời gian không đổi, chống tấn công đo thời gian
    if not hmac.compare_digest(stored_hash, _hash_code(purpose, email, code.strip())):
        return False

    # Giành quyền dùng mã: chỉ 1 request xóa được key thành công
    if not cache.delete(code_key):
        return False
    cache.delete(attempts_key)
    return True
