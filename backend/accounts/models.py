from __future__ import annotations

from typing import Any

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    """3 vai trò cố định của hệ thống (lưu chuỗi ADMIN/MANAGER/EMPLOYEE trong DB)."""

    ADMIN = "ADMIN", "Quản trị viên"
    MANAGER = "MANAGER", "Quản lý"
    EMPLOYEE = "EMPLOYEE", "Nhân viên"


class UserManager(BaseUserManager["User"]):
    """Manager tạo user bằng email thay cho username."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields: Any) -> "User":
        if not email:
            raise ValueError("Email là bắt buộc.")
        # Chuẩn hóa: domain về chữ thường, rồi cả email về chữ thường
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # băm mật khẩu, không lưu bản gốc
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_email_verified", True)
        extra_fields.setdefault("role", Role.ADMIN)
        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser phải có is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser phải có is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    # Tạm dùng chuỗi; Phase 2 sẽ đổi thành ForeignKey tới Department
    department = models.CharField(max_length=100, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)

    is_active = models.BooleanField(default=True)
    is_email_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)  # cho phép vào Django admin
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]  # createsuperuser sẽ hỏi thêm trường này

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.email
