"""API xác thực. View chỉ nhận request, gọi service, trả response."""
from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from common.otp import OTPCooldownError, OTPError, OTPTooManyAttemptsError
from common.permissions import IsAdmin

from . import services
from .models import User
from .throttles import AuthRateThrottle
from .serializers import (
    MessageSerializer,
    TokenPairSerializer,
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
    throttle_classes = [AuthRateThrottle]  # 5 lần/phút/IP


@extend_schema(tags=["Auth"], summary="Đăng ký (gửi OTP)", description="Tạo tài khoản chưa kích hoạt và gửi OTP 6 số về email. Bước tiếp theo: verify-email. Đăng ký lại với email chưa kích hoạt sẽ cập nhật tên và mật khẩu.", responses={201: MessageSerializer, 400: MessageSerializer, 429: MessageSerializer})
class RegisterView(PublicAuthView):
    serializer_class = RegisterSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.register(**serializer.validated_data)
        return Response({"detail": "Mã OTP đã được gửi tới email của bạn."}, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Auth"], summary="Xác thực email bằng OTP", description="Nhập đúng OTP đăng ký thì tài khoản được kích hoạt. Sai tối đa 5 lần mỗi mã.", responses={200: MessageSerializer, 400: MessageSerializer, 429: MessageSerializer})
class VerifyEmailView(PublicAuthView):
    serializer_class = VerifyEmailSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        services.verify_email(email=data["email"], code=data["otp"])
        return Response({"detail": "Kích hoạt tài khoản thành công."})


@extend_schema(tags=["Auth"], summary="Gửi lại OTP", description="purpose là REGISTER hoặc LOGIN. Cách nhau tối thiểu 60 giây (429 kèm Retry-After). Luôn trả kết quả giống nhau dù email có tồn tại hay không. OTP đăng nhập chỉ được gửi sau khi đã qua bước 1.", responses={200: MessageSerializer, 429: MessageSerializer})
class ResendOTPView(PublicAuthView):
    serializer_class = ResendOTPSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.resend_otp(**serializer.validated_data)
        # Luôn trả giống nhau dù email có tồn tại hay không
        return Response({"detail": "Nếu yêu cầu hợp lệ, mã OTP mới đã được gửi."})


@extend_schema(tags=["Auth"], summary="Đăng nhập bước 1/2: mật khẩu", description="Đúng email và mật khẩu thì gửi OTP về email. Chưa trả token. Sai email, sai mật khẩu hoặc chưa kích hoạt đều trả cùng một thông báo 401.", responses={200: MessageSerializer, 401: MessageSerializer, 429: MessageSerializer})
class LoginView(PublicAuthView):
    """Bước 1: kiểm tra mật khẩu, gửi OTP."""

    serializer_class = LoginSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.login_step1(**serializer.validated_data)
        return Response({"detail": "Mã OTP đã được gửi tới email của bạn."})


@extend_schema(tags=["Auth"], summary="Đăng nhập bước 2/2: OTP", description="Nhập đúng OTP (sau khi qua bước 1) để nhận access và refresh token.", responses={200: TokenPairSerializer, 400: MessageSerializer, 429: MessageSerializer})
class LoginVerifyView(PublicAuthView):
    """Bước 2: nhập OTP, nhận access + refresh token."""

    serializer_class = LoginVerifySerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tokens = services.login_step2(email=data["email"], code=data["otp"])
        return Response(tokens)


@extend_schema(tags=["Auth"], summary="Đăng xuất", description="Thu hồi (blacklist) refresh token. Access token hiện tại vẫn dùng được đến khi hết hạn (tối đa 15 phút).", responses={204: None, 400: MessageSerializer})
class LogoutView(ServiceErrorMixin, GenericAPIView):
    """Cần access token hợp lệ (permission mặc định IsAuthenticated)."""

    serializer_class = LogoutSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.logout(user=request.user, refresh_token=serializer.validated_data["refresh"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Auth"], summary="Thông tin người dùng hiện tại")
class MeView(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):  # type: ignore[no-untyped-def]
        return self.request.user


@extend_schema(tags=["Users"], summary="Danh sách người dùng (chỉ ADMIN)", responses={200: UserSerializer(many=True), 403: MessageSerializer})
class UserListView(ListAPIView):
    """Danh sách người dùng. Chỉ ADMIN."""

    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    queryset = User.objects.all()
