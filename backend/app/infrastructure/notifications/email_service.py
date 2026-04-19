import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.config import get_settings
from app.logger import get_logger

logger = get_logger("app.infrastructure.notifications.email_service")


class EmailDeliveryError(RuntimeError):
    """Raised when SMTP delivery fails."""


class SMTPEmailService:
    """Minimal SMTP email sender for password reset links."""

    def __init__(self):
        self._settings = get_settings()

    def is_configured(self) -> bool:
        return bool(self._settings.SMTP_HOST and self._settings.SMTP_FROM_EMAIL)

    async def send_password_reset_email(
        self,
        recipient_email: str,
        recipient_name: str,
        reset_url: str,
        expire_minutes: int,
    ) -> None:
        if not self.is_configured():
            raise EmailDeliveryError("SMTP chưa được cấu hình")

        greeting_name = recipient_name.strip() or recipient_email
        subject = "Đặt lại mật khẩu CV Review"
        body = (
            f"Chào {greeting_name},\n\n"
            "Chúng tôi đã nhận được yêu cầu đặt lại mật khẩu cho tài khoản CV Review của bạn.\n"
            f"Nhấn vào liên kết sau để tạo mật khẩu mới: {reset_url}\n\n"
            f"Liên kết này sẽ hết hạn sau {expire_minutes} phút và chỉ dùng được một lần.\n"
            "Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này.\n"
        )

        await asyncio.to_thread(self._send_plain_text_email, recipient_email, subject, body)

    def _send_plain_text_email(self, recipient_email: str, subject: str, body: str) -> None:
        settings = self._settings
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
        message["To"] = recipient_email
        message.set_content(body)

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                smtp.ehlo()
                if settings.SMTP_USE_TLS:
                    smtp.starttls()
                    smtp.ehlo()
                if settings.SMTP_USERNAME:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(message)
        except Exception as exc:
            logger.error("SMTP send failed: %s", exc, exc_info=True)
            raise EmailDeliveryError("Không thể gửi email đặt lại mật khẩu") from exc
