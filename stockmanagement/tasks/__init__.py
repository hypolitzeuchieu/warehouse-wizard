"""Celery tasks for RetailPulse."""

__all__ = [
    "send_email",
    "send_otp_email_task",
    "send_otp_sms_task",
    "send_password_reset_email_task",
    "send_password_reset_sms_task",
    "check_expired_products",
    "cleanup_expired_tokens",
    "send_notification_task",
]


def _lazy_imports():
    """Lazy import tasks to avoid circular dependencies."""
    from tasks.auth_tasks import cleanup_expired_tokens  # noqa: F401
    from tasks.inventory_tasks import check_expired_products  # noqa: F401
    from tasks.notification_tasks import send_notification_task  # noqa: F401
    from tasks.otp_tasks import send_otp_email_task, send_otp_sms_task  # noqa: F401
    from tasks.password_reset_tasks import (  # noqa: F401
        send_password_reset_email_task,
        send_password_reset_sms_task,
    )
    from tasks.send_mail import send_email  # noqa: F401
