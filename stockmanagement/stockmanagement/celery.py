from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stockmanagement.settings")

app = Celery("stockmanagement")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

try:
    from tasks.otp_tasks import send_otp_email_task, send_otp_sms_task
    from tasks.password_reset_tasks import (
        send_password_reset_email_task,
        send_password_reset_sms_task,
    )
    from tasks.send_mail import send_email

    __all__ = [
        "send_email",
        "send_otp_email_task",
        "send_otp_sms_task",
        "send_password_reset_email_task",
        "send_password_reset_sms_task",
    ]
except ImportError:
    pass
