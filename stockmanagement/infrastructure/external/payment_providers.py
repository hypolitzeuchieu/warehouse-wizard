"""Payment provider interfaces and implementations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any
from uuid import UUID

import requests
import stripe

logger = logging.getLogger(__name__)


class PaymentProviderInterface(ABC):
    """Interface for payment providers."""

    @abstractmethod
    def initiate_payment(
        self,
        amount: Decimal,
        currency: str,
        subscription_id: UUID,
        return_url: str | None = None,
        cancel_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Initiate a payment transaction.

        Args:
            amount: Payment amount
            currency: Currency code (e.g., 'XAF', 'USD')
            subscription_id: Subscription ID
            return_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment
            metadata: Additional metadata

        Returns:
            Dictionary with payment details including:
            - transaction_id: External transaction ID
            - payment_url: URL for redirect (if applicable)
            - status: Payment status
        """
        pass

    @abstractmethod
    def verify_payment(self, transaction_id: str) -> dict[str, Any]:
        """
        Verify payment status.

        Args:
            transaction_id: External transaction ID

        Returns:
            Dictionary with payment status including:
            - status: Payment status
            - amount: Payment amount
            - currency: Currency code
        """
        pass

    @abstractmethod
    def handle_webhook(
        self, payload: dict[str, Any], signature: str | None = None
    ) -> dict[str, Any]:
        """
        Handle webhook from payment provider.

        Args:
            payload: Webhook payload
            signature: Webhook signature for verification

        Returns:
            Dictionary with webhook event details
        """
        pass


class StripeService(PaymentProviderInterface):
    """Stripe payment service implementation."""

    def __init__(
        self, secret_key: str, publishable_key: str, webhook_secret: str | None = None
    ):
        """Initialize Stripe service."""
        try:
            self.stripe = stripe
            stripe.api_key = secret_key
            self.publishable_key = publishable_key
            self.webhook_secret = webhook_secret
        except ImportError as err:
            raise ImportError("Stripe service unavailable. Try again later.") from err

    def initiate_payment(
        self,
        amount: Decimal,
        currency: str,
        subscription_id: UUID,
        return_url: str | None = None,
        cancel_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Initiate Stripe payment via Checkout Session."""
        try:
            currency_upper = currency.upper()
            zero_decimal_currencies = {
                "XAF",
                "XOF",
                "JPY",
                "KRW",
                "CLP",
                "VND",
                "UGX",
                "TZS",
            }

            if currency_upper in zero_decimal_currencies:
                amount_stripe = int(float(amount))
                logger.info(
                    f"Using zero-decimal currency {currency_upper}, amount: {amount_stripe}"
                )
            else:
                amount_stripe = int(float(amount) * 100)
                logger.info(
                    f"Using decimal currency {currency_upper}, amount in cents: {amount_stripe}"
                )

            session_data = {
                "payment_method_types": ["card"],
                "line_items": [
                    {
                        "price_data": {
                            "currency": currency.lower(),
                            "product_data": {
                                "name": f"Subscription {subscription_id}",
                            },
                            "unit_amount": amount_stripe,
                        },
                        "quantity": 1,
                    }
                ],
                "mode": "payment",
                "success_url": return_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "subscription_id": str(subscription_id),
                    **(metadata or {}),
                },
                # Add payment_intent_data to pass metadata to payment_intent
                "payment_intent_data": {
                    "metadata": {
                        "subscription_id": str(subscription_id),
                        **(metadata or {}),
                    },
                },
            }

            session = self.stripe.checkout.Session.create(**session_data)

            try:
                if session.payment_intent:
                    self.stripe.PaymentIntent.modify(
                        session.payment_intent,
                        metadata={
                            "subscription_id": str(subscription_id),
                            "checkout_session_id": session.id,
                            "session_id": session.id,  # Alias for easier lookup
                            **(metadata or {}),
                        },
                    )
            except Exception as e:
                logger.warning(f"Could not update payment_intent metadata: {e}")

            return {
                "transaction_id": session.id,
                "payment_url": session.url,
                "status": "pending",
                "provider": "stripe",
            }
        except Exception as e:
            logger.error(f"Stripe payment initiation failed: {e}", exc_info=True)
            raise

    def verify_payment(self, transaction_id: str) -> dict[str, Any]:
        """Verify Stripe payment status."""
        try:
            session = self.stripe.checkout.Session.retrieve(transaction_id)
            payment_intent_id = session.payment_intent

            if payment_intent_id:
                payment_intent = self.stripe.PaymentIntent.retrieve(payment_intent_id)
                currency_code = payment_intent.currency.upper()
                zero_decimal_currencies = {
                    "XAF",
                    "XOF",
                    "JPY",
                    "KRW",
                    "CLP",
                    "VND",
                    "UGX",
                    "TZS",
                }
                has_decimals = currency_code not in zero_decimal_currencies

                amount_raw = payment_intent.amount
                if has_decimals:
                    amount_value = Decimal(amount_raw) / 100
                else:
                    amount_value = Decimal(amount_raw)

                return {
                    "status": payment_intent.status,
                    "amount": amount_value,
                    "currency": currency_code,
                }
            else:
                return {
                    "status": session.payment_status,
                    "amount": None,
                    "currency": None,
                }
        except Exception as e:
            logger.error(f"Stripe payment verification failed: {e}", exc_info=True)
            raise

    def handle_webhook(
        self, payload: dict[str, Any], signature: str | None = None
    ) -> dict[str, Any]:
        """Handle Stripe webhook."""
        try:
            if isinstance(payload, dict) and "type" in payload:
                event = payload
            elif signature and self.webhook_secret:
                event = self.stripe.Webhook.construct_event(
                    payload, signature, self.webhook_secret
                )
            else:
                # For testing or if webhook secret is not configured
                event = payload

            event_type = event.get("type")
            data = event.get("data", {}).get("object", {})

            transaction_id = None
            if event_type == "checkout.session.completed":
                # For checkout.session, use the session ID (this is what we save)
                transaction_id = data.get("id")
            elif event_type in (
                "payment_intent.succeeded",
                "payment_intent.payment_failed",
            ):
                # For payment_intent, try to get session_id from metadata
                metadata = data.get("metadata", {})
                transaction_id = metadata.get("session_id") or metadata.get(
                    "checkout_session_id"
                )

                # If not in metadata, try to retrieve the payment_intent to get updated metadata
                if not transaction_id:
                    try:
                        payment_intent = self.stripe.PaymentIntent.retrieve(
                            data.get("id")
                        )
                        payment_metadata = payment_intent.metadata or {}
                        transaction_id = payment_metadata.get(
                            "session_id"
                        ) or payment_metadata.get("checkout_session_id")
                    except Exception as e:
                        logger.warning(
                            f"Could not retrieve payment_intent {data.get('id')}: {e}"
                        )

                # Fallback: if still not found, log warning and use payment_intent.id
                # (this won't match, but at least we log it)
                if not transaction_id:
                    logger.warning(
                        f"Could not find session_id for payment_intent event {event_type}. "
                        f"PaymentIntent ID: {data.get('id')}, metadata: {metadata}"
                    )
                    transaction_id = data.get("id")
            elif event_type in ("charge.succeeded", "charge.failed"):
                # For charge, get payment_intent first, then try to get session_id from metadata
                payment_intent_id = data.get("payment_intent")
                if payment_intent_id:
                    try:
                        payment_intent = self.stripe.PaymentIntent.retrieve(
                            payment_intent_id
                        )
                        payment_metadata = payment_intent.metadata or {}
                        transaction_id = payment_metadata.get(
                            "session_id"
                        ) or payment_metadata.get("checkout_session_id")
                    except Exception as e:
                        logger.warning(
                            f"Could not retrieve payment_intent {payment_intent_id}: {e}"
                        )
                # Fallback to charge ID if session_id not found
                if not transaction_id:
                    logger.warning(
                        f"Could not find session_id for charge event {event_type}. "
                        f"Charge ID: {data.get('id')}, PaymentIntent ID: {payment_intent_id}"
                    )
                    transaction_id = data.get("id")
            else:
                # For other events, use the object ID as fallback
                transaction_id = data.get("id")
                logger.info(
                    f"Using default transaction_id extraction for event {event_type}: {transaction_id}"
                )

            payment_status = data.get("payment_status") or data.get("status", "")
            if payment_status in ("paid", "succeeded"):
                mapped_status = "completed"
            elif payment_status in ("unpaid", "requires_payment_method"):
                mapped_status = "pending"
            else:
                mapped_status = payment_status.lower() if payment_status else "pending"

            # Log transaction_id extraction for debugging
            if transaction_id:
                logger.info(
                    f"Extracted transaction_id '{transaction_id}' from event '{event_type}'"
                )
            else:
                logger.warning(
                    f"Could not extract transaction_id from event '{event_type}'. "
                    f"Event data ID: {data.get('id', 'N/A')}"
                )

            # Determine if currency has decimals
            currency_code = data.get("currency", "").upper()
            zero_decimal_currencies = {
                "XAF",
                "XOF",
                "JPY",
                "KRW",
                "CLP",
                "VND",
                "UGX",
                "TZS",
            }
            has_decimals = currency_code not in zero_decimal_currencies

            amount_raw = data.get("amount_total") or data.get("amount", 0)
            if amount_raw:
                if has_decimals:
                    amount_value = Decimal(amount_raw) / 100
                else:
                    amount_value = Decimal(amount_raw)
            else:
                amount_value = None

            return {
                "event_type": event_type,
                "transaction_id": transaction_id,
                "status": mapped_status,
                "amount": amount_value,
                "currency": currency_code if currency_code else None,
                "metadata": data.get("metadata", {}),
            }
        except Exception as e:
            logger.error(f"Stripe webhook handling failed: {e}", exc_info=True)
            raise


class MTNMobileMoneyService(PaymentProviderInterface):
    """MTN Mobile Money service implementation."""

    def __init__(self, api_key: str, api_url: str, api_user_id: str | None = None):
        """Initialize MTN Mobile Money service."""

        self.requests = requests
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.api_user_id = api_user_id

    def initiate_payment(
        self,
        amount: Decimal,
        currency: str,
        subscription_id: UUID,
        return_url: str | None = None,
        cancel_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Initiate MTN Mobile Money payment."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "amount": str(amount),
                "currency": currency,
                "externalId": str(subscription_id),
                "payer": {
                    "partyIdType": "MSISDN",
                    "partyId": metadata.get("phone_number", "") if metadata else "",
                },
                "payerMessage": f"Subscription payment for {subscription_id}",
                "payeeNote": f"Subscription {subscription_id}",
            }

            response = self.requests.post(
                f"{self.api_url}/collection/v1_0/requesttopay",
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 202:
                transaction_id = response.headers.get("X-Reference-Id")
                return {
                    "transaction_id": transaction_id,
                    "payment_url": None,
                    "status": "pending",
                    "provider": "mtn_mobile_money",
                }
            else:
                error_data = response.json() if response.text else {}
                raise Exception(f"MTN API error: {error_data}")

        except Exception as e:
            logger.error(
                f"MTN Mobile Money payment initiation failed: {e}", exc_info=True
            )
            raise

    def verify_payment(self, transaction_id: str) -> dict[str, Any]:
        """Verify MTN Mobile Money payment status."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }

            response = self.requests.get(
                f"{self.api_url}/collection/v1_0/requesttopay/{transaction_id}",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "status": data.get("status", "pending"),
                    "amount": Decimal(data.get("amount", 0)),
                    "currency": data.get("currency", "XAF"),
                }
            else:
                raise Exception(f"MTN API error: {response.text}")

        except Exception as e:
            logger.error(
                f"MTN Mobile Money payment verification failed: {e}", exc_info=True
            )
            raise

    def handle_webhook(
        self, payload: dict[str, Any], signature: str | None = None
    ) -> dict[str, Any]:
        """Handle MTN Mobile Money webhook."""
        # MTN webhook structure may vary - adjust based on actual implementation
        return {
            "event_type": payload.get("eventType", "payment.completed"),
            "transaction_id": payload.get("externalId") or payload.get("transactionId"),
            "status": payload.get("status", "pending"),
            "amount": Decimal(payload.get("amount", 0)),
            "currency": payload.get("currency", "XAF"),
            "metadata": payload.get("metadata", {}),
        }


class OrangeMobileMoneyService(PaymentProviderInterface):
    """Orange Mobile Money service implementation."""

    def __init__(self, api_key: str, api_url: str, merchant_key: str | None = None):
        """Initialize Orange Mobile Money service."""

        self.requests = requests
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.merchant_key = merchant_key

    def initiate_payment(
        self,
        amount: Decimal,
        currency: str,
        subscription_id: UUID,
        return_url: str | None = None,
        cancel_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Initiate Orange Mobile Money payment."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "merchant_key": self.merchant_key,
                "currency": currency,
                "order_id": str(subscription_id),
                "amount": str(amount),
                "return_url": return_url,
                "cancel_url": cancel_url,
                "notif_url": metadata.get("webhook_url", "") if metadata else "",
                "lang": "fr",
                "reference": f"SUB_{subscription_id}",
            }

            response = self.requests.post(
                f"{self.api_url}/api/ecommerce/v1/payments/order",
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 201:
                data = response.json()
                return {
                    "transaction_id": data.get("pay_token"),
                    "payment_url": data.get("payment_url"),
                    "status": "pending",
                    "provider": "orange_mobile_money",
                }
            else:
                error_data = response.json() if response.text else {}
                raise Exception(f"Orange API error: {error_data}")

        except Exception as e:
            logger.error(
                f"Orange Mobile Money payment initiation failed: {e}", exc_info=True
            )
            raise

    def verify_payment(self, transaction_id: str) -> dict[str, Any]:
        """Verify Orange Mobile Money payment status."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }

            response = self.requests.get(
                f"{self.api_url}/api/ecommerce/v1/payments/{transaction_id}",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "status": data.get("status", "pending"),
                    "amount": Decimal(data.get("amount", 0)),
                    "currency": data.get("currency", "XAF"),
                }
            else:
                raise Exception(f"Orange API error: {response.text}")

        except Exception as e:
            logger.error(
                f"Orange Mobile Money payment verification failed: {e}", exc_info=True
            )
            raise

    def handle_webhook(
        self, payload: dict[str, Any], signature: str | None = None
    ) -> dict[str, Any]:
        """Handle Orange Mobile Money webhook."""
        return {
            "event_type": payload.get("eventType", "payment.completed"),
            "transaction_id": payload.get("pay_token") or payload.get("transactionId"),
            "status": payload.get("status", "pending"),
            "amount": Decimal(payload.get("amount", 0)),
            "currency": payload.get("currency", "XAF"),
            "metadata": payload.get("metadata", {}),
        }
