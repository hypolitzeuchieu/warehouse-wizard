"""Email service implementation."""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails."""

    @staticmethod
    def send_otp_email(email: str, otp_code: str, purpose: str = "verification") -> bool:
        """
        Send OTP via email.

        Args:
            email: Recipient email address
            otp_code: OTP code to send
            purpose: Purpose of OTP (signup, login, etc.)

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            subject = "Your RetailPulse Verification Code"
            if purpose == "signup":
                subject = "Welcome to RetailPulse - Verify Your Account"
            elif purpose == "login":
                subject = "Your RetailPulse Login Code"
            elif purpose == "password_reset":
                subject = "RetailPulse Password Reset Code"

            message = f"Your verification code is: {otp_code}\n\nThis code will expire in 10 minutes.\n\nIf you didn't request this code, please ignore this email."

            from_email = settings.EMAIL_HOST_USER
            recipient_list = [email]

            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False,
            )

            logger.info(f"OTP email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send OTP email to {email}: {str(e)}")
            return False

    @staticmethod
    def send_welcome_email(email: str, username: str) -> bool:
        """Send welcome email to new user."""
        try:
            subject = "Welcome to RetailPulse!"
            message = f"Hello {username},\n\nWelcome to RetailPulse! Your account has been successfully created.\n\nBest regards,\nThe RetailPulse Team"

            from_email = settings.EMAIL_HOST_USER
            recipient_list = [email]

            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False,
            )

            logger.info(f"Welcome email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send welcome email to {email}: {str(e)}")
            return False

    @staticmethod
    def send_password_reset_email(email: str, reset_url: str, token: str) -> bool:
        """Send password reset email with link."""
        try:
            subject = "RetailPulse Password Reset"
            message = f"Hello,\n\nYou requested a password reset. Click the link below to reset your password:\n\n{reset_url}\n\nThis link will expire in 10 minutes.\n\nIf you didn't request this, please ignore this email.\n\nBest regards,\nThe RetailPulse Team"

            from_email = settings.EMAIL_HOST_USER
            recipient_list = [email]

            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False,
            )

            logger.info(f"Password reset email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {str(e)}")
            return False

