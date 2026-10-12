"""Hàm bọc DUY NHẤT để gửi email. Không gọi send_mail trực tiếp ở nơi khác.

Phase 6 chỉ cần sửa bên trong `_deliver` thành task Celery (`.delay`),
chữ ký của `send_email` giữ nguyên nên nơi gọi không phải đổi.
"""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string


def _deliver(to: str, subject: str, template: str, context: dict[str, Any]) -> None:
    """Render 2 bản (text + HTML) rồi gửi qua SMTP."""
    text_body = render_to_string(f"emails/{template}.txt", context)
    html_body = render_to_string(f"emails/{template}.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,  # bản text: client không hiển thị được HTML sẽ dùng bản này
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
    )
    message.attach_alternative(html_body, "text/html")
    message.send()


def send_email(
    to: str,
    subject: str,
    template: str,
    context: dict[str, Any] | None = None,
) -> None:
    """Gửi email sau khi transaction hiện tại commit.

    Args:
        to: địa chỉ người nhận.
        subject: tiêu đề.
        template: tên template không có đuôi, ví dụ "otp" -> emails/otp.txt + emails/otp.html.
        context: biến truyền vào template. `frontend_url` luôn được thêm sẵn.
    """
    full_context = {"frontend_url": settings.FRONTEND_URL, **(context or {})}
    # Đang trong transaction.atomic thì chờ commit; không có transaction thì chạy ngay
    transaction.on_commit(lambda: _deliver(to, subject, template, full_context))
