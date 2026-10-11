"""API xác thực. View chỉ nhận request, gọi service, trả response."""
from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.generics import GenericAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from common.otp import OTPCooldownError, OTPError, OTPTooManyAttemptsError

from . import services
from .serializers import (
    LoginSerializer,
    LoginVerifySerializer,
    LogoutSerializer,
    RegisterSerializer,
    ResendOTPSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)


class ServiceErrorMixin:
    """Dịch lỗi nghiệp vụ sang HTTP ở một chỗ duy nhất."""

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, OTPCooldownError):
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(exc.retry_after)},
            )
        if isinstance(exc, OTPTooManyAttemptsError):
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if isinstance(exc, services.EmailAlreadyRegisteredError):
            return Response({"detail": "Email đã được đăng ký."}, status=status.HTTP_400_BAD_REQUEST)
        if isinstance(exc, services.InvalidCredentialsError):
            return Response(
                {"detail": "Email hoặc mật khẩu không đúng."}, status=status.HTTP_401_UNAUTHORIZED
            )
        if isinstance(exc, services.InvalidOTPError):
            return Response(
                {"detail": "Mã OTP không hợp lệ hoặc đã hết hạn."}, status=status.HTTP_400_BAD_REQUEST
            )
        if isinstance(exc, services.InvalidRefreshTokenError):
            return Response({"detail": "Refresh token không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
        if isinstance(exc, OTPError):  # dự phòng cho lỗi OTP khác
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)  # type: ignore[misc]


class PublicAuthView(ServiceErrorMixin, GenericAPIView):
    """Base cho API công khai: không cần token, và bỏ qua token (hết hạn) gửi kèm."""

    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []


class RegisterView(PublicAuthView):
    serializer_class = RegisterSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.register(**serializer.validated_data)
        return Response({"detail": "Mã OTP đã được gửi tới email của bạn."}, status=status.HTTP_201_CREATED)


class VerifyEmailView(PublicAuthView):
    serializer_class = VerifyEmailSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        services.verify_email(email=data["email"], code=data["otp"])
        return Response({"detail": "Kích hoạt tài khoản thành công."})


class ResendOTPView(PublicAuthView):
    serializer_class = ResendOTPSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.resend_otp(**serializer.validated_data)
        # Luôn trả giống nhau dù email có tồn tại hay không
        return Response({"detail": "Nếu yêu cầu hợp lệ, mã OTP mới đã được gửi."})


class LoginView(PublicAuthView):
    """Bước 1: kiểm tra mật khẩu, gửi OTP."""

    serializer_class = LoginSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.login_step1(**serializer.validated_data)
        return Response({"detail": "Mã OTP đã được gửi tới email của bạn."})


class LoginVerifyView(PublicAuthView):
    """Bước 2: nhập OTP, nhận access + refresh token."""

    serializer_class = LoginVerifySerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tokens = services.login_step2(email=data["email"], code=data["otp"])
        return Response(tokens)


class LogoutView(ServiceErrorMixin, GenericAPIView):
    """Cần access token hợp lệ (permission mặc định IsAuthenticated)."""

    serializer_class = LogoutSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.logout(user=request.user, refresh_token=serializer.validated_data["refresh"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):  # type: ignore[no-untyped-def]
        return self.request.user
