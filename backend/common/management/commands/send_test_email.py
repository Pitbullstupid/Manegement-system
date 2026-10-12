"""Lệnh kiểm tra cấu hình email: python manage.py send_test_email <email>."""
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.core.validators import validate_email


class Command(BaseCommand):
    help = "Gửi một email thử (text + HTML) để kiểm tra cấu hình SMTP/Mailpit."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("email", type=str, help="Địa chỉ email người nhận")

    def handle(self, *args: Any, **options: Any) -> None:
        recipient: str = options["email"]

        # Kiểm tra định dạng email trước khi gửi
        try:
            validate_email(recipient)
        except ValidationError as exc:
            raise CommandError(f"Email không hợp lệ: {recipient}") from exc

        text_body = (
            "Xin chào,\n\n"
            "Đây là email thử từ hệ thống quản lý dự án.\n"
            "Nếu bạn đọc được dòng này, cấu hình email đã hoạt động.\n"
        )
        html_body = (
            "<h2>Xin chào,</h2>"
            "<p>Đây là email thử từ <b>hệ thống quản lý dự án</b>.</p>"
            "<p>Nếu bạn thấy chữ <b>đậm</b> ở đây, bản HTML hoạt động.</p>"
        )

        message = EmailMultiAlternatives(
            subject="[Test] Kiểm tra gửi email từ hệ thống",
            body=text_body,  # bản text (dự phòng)
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        message.attach_alternative(html_body, "text/html")  # bản HTML

        try:
            sent = message.send(fail_silently=False)
        except OSError as exc:
            # Connection refused, timeout, lỗi SMTP... đều là lớp con của OSError
            raise CommandError(
                f"Không gửi được tới {settings.EMAIL_HOST}:{settings.EMAIL_PORT}. "
                f"Mailpit đã chạy chưa? Chi tiết: {exc}"
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Đã gửi {sent} email tới {recipient} qua "
                f"{settings.EMAIL_HOST}:{settings.EMAIL_PORT}. "
                "Mở giao diện Mailpit (mặc định http://localhost:8025) để xem."
            )
        )