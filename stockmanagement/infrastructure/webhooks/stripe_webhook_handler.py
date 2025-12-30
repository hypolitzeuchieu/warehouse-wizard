"""Stripe webhook handler."""

import json
import logging
from typing import Any

import stripe
from django.conf import settings
from django.http import HttpRequest

logger = logging.getLogger(__name__)


def handle_stripe_webhook(request: HttpRequest) -> dict[str, Any]:
    """
    Handle Stripe webhook events.

    Args:
        request: Django HTTP request with webhook payload

    Returns:
        Dictionary with webhook processing result
    """
    try:
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        try:
            payload_json = json.loads(payload.decode("utf-8"))
            logger.info("STRIPE WEBHOOK RAW DATA (JSON):")
            logger.info(json.dumps(payload_json, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Could not parse webhook payload as JSON: {e}")
            logger.info(f"Raw payload (bytes): {payload}")
            return {"error": "Invalid JSON payload"}

        if not sig_header:
            logger.warning("Stripe webhook missing signature header")
            return {"error": "Missing signature header"}

        webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
        if not webhook_secret:
            logger.warning("Stripe webhook secret not configured")
            return {"error": "Webhook secret not configured"}

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError as e:
            logger.error(f"Invalid Stripe webhook payload: {e}")
            return {"error": "Invalid payload"}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid Stripe webhook signature: {e}")
            logger.error(f"Webhook secret configured: {bool(webhook_secret)}")
            logger.error(f"Signature header present: {bool(sig_header)}")
            return {"error": "Invalid signature"}

        # Extract event data
        event_type = event.get("type")

        logger.info(f"Stripe webhook received: {event_type}")

        # Log parsed event data
        logger.info("STRIPE WEBHOOK PARSED EVENT DATA:")
        logger.info(json.dumps(event, indent=2, ensure_ascii=False, default=str))

        return {
            "event_type": event_type,
            "payload": event,
            "signature": sig_header,
        }

    except ImportError:
        logger.error("stripe package not installed")
        return {"error": "Stripe package not installed"}
    except Exception as e:
        logger.error(f"Stripe webhook handling failed: {e}", exc_info=True)
        return {"error": str(e)}
