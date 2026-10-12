"""Logic nghiệp vụ xác thực. Views chỉ gọi hàm ở đây rồi dịch lỗi sang HTTP."""
from __future__ import annotations

from functools import lru_cache
from typing import TypedDict

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from common.email import send_email
from common.otp import OTPPurpose, issue_otp, verify_otp

from .models import User


class AuthServiceError(Exception):
    """Lớp cha cho các lỗi nghiệp vụ xác thực."""


class EmailAlreadyRegisteredError(AuthServiceError):
    """Email đã đăng ký và đã kích hoạt."""


class InvalidCredentialsError(AuthServiceError):
    """Sai email, sai mật khẩu hoặc tài khoản chưa kích hoạt (không phân biệt)."""


class InvalidOTPError(AuthServiceError):
    """OTP sai, hết hạn, đã dùng hoặc chưa từng gửi (không phân biệt)."""


class InvalidRefreshTokenError(AuthServiceError):
    """Refresh token không hợp lệ, hết hạn hoặc đã bị thu hồi."""


class TokenPair(TypedDict):
    access: str
    refresh: str


_PURPOSE_LABEL = {OTPPurpose.REGISTER: "đăng ký", OTPPurpose.LOGIN: "đăng nhập"}
_PURPOSE_SUBJECT = {
    OTPPurpose.REGISTER: "Mã xác thực đăng ký tài khoản",
    OTPPurpose.LOGIN: "Mã xác thực đăng nhập",
}


def _normalize(email: str) -> str:
    return email.strip().lower()


def _login_pending_key(email: str) -> str:
    # Cờ "đã qua bước 1 (đúng mật khẩu)". Thiếu cờ này thì bước 2 và gửi lại OTP đăng nhập bị từ chối.
    return f"login_pending:{_normalize(email)}"


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    # Băm giả, tạo một lần: dùng để email không tồn tại cũng tốn thời gian kiểm tra như email thật
    return make_password("dummy-password-for-timing")


def _send_otp_email(purpose: str, email: str, code: str) -> None:
    send_email(
        to=email,
        subject=_PURPOSE_SUBJECT[purpose],
        template="otp",
        context={
            "code": code,
            "purpose_label": _PURPOSE_LABEL[purpose],
            "ttl_minutes": settings.OTP_TTL_SECONDS // 60,
        },
    )


@transaction.atomic
def register(*, email: str, password: str, full_name: str) -> None:
    """Tạo user chưa kích hoạt (hoặc làm lại đăng ký dở) rồi gửi OTP.

    Raises:
        EmailAlreadyRegisteredError: email đã kích hoạt.
        OTPCooldownError: gửi lại quá nhanh (toàn bộ thay đổi bị rollback).
    """
    email = _normalize(email)
    user = User.objects.select_for_update().filter(email=email).first()

    if user is not None and user.is_email_verified:
        raise EmailAlreadyRegisteredError

    if user is None:
        User.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            is_active=False,
            is_email_verified=False,
        )
    else:  # đăng ký dở trước đó: cho làm lại bằng tên + mật khẩu mới
        user.full_name = full_name
        user.set_password(password)
        user.save(update_fields=["full_name", "password"])

    code = issue_otp(OTPPurpose.REGISTER, email)
    _send_otp_email(OTPPurpose.REGISTER, email, code)


@transaction.atomic
def verify_email(*, email: str, code: str) -> None:
    """Nhập đúng OTP đăng ký thì kích hoạt tài khoản.

    Raises:
        InvalidOTPError: OTP không đúng.
        OTPTooManyAttemptsError: sai quá số lần cho phép.
    """
    email = _normalize(email)
    if not verify_otp(OTPPurpose.REGISTER, email, code):
        raise InvalidOTPError

    updated = User.objects.filter(email=email, is_email_verified=False).update(
        is_active=True, is_email_verified=True
    )
    if not updated:
        raise InvalidOTPError


def resend_otp(*, purpose: str, email: str) -> None:
    """Gửi lại OTP. Luôn trả kết quả giống nhau dù email có tồn tại hay không.

    Raises:
        OTPCooldownError: gửi lại trong thời gian chờ.
    """
    email = _normalize(email)
    # Chỉ phát hành mã khi đủ điều kiện, nếu không kẻ lạ gọi resend sẽ bật cooldown và chặn người thật.
    # Email lạ hoặc chưa đủ điều kiện vẫn nhận câu trả lời giống hệt (không lộ thông tin).
    # (mã được tạo ở cuối hàm, chỉ khi eligible)

    user = User.objects.filter(email=email).first()
    if user is None:
        return

    if purpose == OTPPurpose.REGISTER:
        eligible = not user.is_email_verified
    else:
        # Đăng nhập: bắt buộc đã qua bước 1 (đúng mật khẩu)
        eligible = (
            user.is_active
            and user.is_email_verified
            and cache.get(_login_pending_key(email)) is not None
        )

    if eligible:
        _send_otp_email(purpose, email, issue_otp(purpose, email))


def login_step1(*, email: str, password: str) -> None:
    """Đúng email + mật khẩu thì gửi OTP.

    Raises:
        InvalidCredentialsError: sai email/mật khẩu hoặc chưa kích hoạt.
        OTPCooldownError: gửi lại quá nhanh.
    """
    email = _normalize(email)
    user = User.objects.filter(email=email).first()

    if user is None:
        check_password(password, _dummy_hash())  # cân bằng thời gian phản hồi
        raise InvalidCredentialsError

    password_ok = user.check_password(password)
    if not (password_ok and user.is_active and user.is_email_verified):
        raise InvalidCredentialsError

    code = issue_otp(OTPPurpose.LOGIN, email)
    cache.set(_login_pending_key(email), 1, timeout=settings.OTP_TTL_SECONDS)
    _send_otp_email(OTPPurpose.LOGIN, email, code)


def login_step2(*, email: str, code: str) -> TokenPair:
    """Nhập đúng OTP đăng nhập thì cấp access + refresh token.

    Raises:
        InvalidOTPError: OTP sai, hoặc chưa qua bước 1.
        OTPTooManyAttemptsError: sai quá số lần cho phép.
    """
    email = _normalize(email)
    pending_key = _login_pending_key(email)

    if cache.get(pending_key) is None:  # chưa qua bước 1
        raise InvalidOTPError
    if not verify_otp(OTPPurpose.LOGIN, email, code):
        raise InvalidOTPError

    user = User.objects.filter(email=email, is_active=True, is_email_verified=True).first()
    if user is None:
        raise InvalidOTPError

    cache.delete(pending_key)  # mỗi lần qua bước 1 chỉ đổi được một lần token
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def logout(*, user: User, refresh_token: str) -> None:
    """Thu hồi (blacklist) refresh token của chính user đang đăng nhập.

    Raises:
        InvalidRefreshTokenError: token sai, hết hạn, đã thu hồi, hoặc của người khác.
    """
    try:
        token = RefreshToken(refresh_token)  # tự kiểm tra chữ ký, hạn dùng, blacklist
    except TokenError as exc:
        raise InvalidRefreshTokenError from exc

    if str(token.get("user_id")) != str(user.pk):
        raise InvalidRefreshTokenError
    token.blacklist()
