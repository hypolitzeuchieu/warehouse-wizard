"""Mobile Money webhook handler."""

import json
import logging
from typing import Any

from django.http import HttpRequest

logger = logging.getLogger(__name__)


def handle_mobile_money_webhook(request: HttpRequest, provider: str) -> dict[str, Any]:
    """
    Handle Mobile Money webhook events (MTN or Orange).

    Args:
        request: Django HTTP request with webhook payload
        provider: Payment provider ('mtn_mobile_money' or 'orange_mobile_money')

    Returns:
        Dictionary with webhook processing result
    """
    try:
        # Parse request body
        try:
            if hasattr(request, "json"):
                payload = request.json
            else:
                payload = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Invalid Mobile Money webhook payload: {e}")
            return {"error": "Invalid payload"}

        # Extract signature if present
        signature = request.META.get("HTTP_X_SIGNATURE") or request.META.get(
            "HTTP_SIGNATURE"
        )
        logger.info(json.dumps(payload, indent=2, ensure_ascii=False))
        logger.info(f"Mobile Money webhook received from {provider}")

        return {
            "event_type": payload.get("eventType", "payment.completed"),
            "payload": payload,
            "signature": signature,
        }

    except Exception as e:
        logger.error(f"Mobile Money webhook handling failed: {e}", exc_info=True)
        return {"error": str(e)}
