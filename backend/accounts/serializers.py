"""Kiểm tra dữ liệu đầu vào cho các API xác thực. Không chứa logic nghiệp vụ."""
from __future__ import annotations

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from common.otp import OTPPurpose

from .models import User


class _EmailMixin(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class RegisterSerializer(_EmailMixin):
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate_password(self, value: str) -> str:
        # Dùng đúng các quy tắc AUTH_PASSWORD_VALIDATORS trong settings
        try:
            password_validation.validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class VerifyEmailSerializer(_EmailMixin):
    otp = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Mã OTP gồm đúng 6 chữ số."})


class ResendOTPSerializer(_EmailMixin):
    purpose = serializers.ChoiceField(choices=OTPPurpose.choices)


class LoginSerializer(_EmailMixin):
    # Không kiểm tra độ mạnh ở đây: chỉ so với mật khẩu đã lưu
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)


class LoginVerifySerializer(VerifyEmailSerializer):
    pass


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class TokenPairSerializer(serializers.Serializer):
    """Chỉ để mô tả response trong Swagger."""

    access = serializers.CharField()
    refresh = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "department", "role", "is_email_verified", "date_joined"]
        read_only_fields = fields
