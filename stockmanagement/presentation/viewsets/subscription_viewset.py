"""Subscription ViewSet using DDD architecture with use cases."""

from __future__ import annotations

import logging
from uuid import UUID

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.dto.subscription_dto import WebhookPayloadDTO
from application.use_cases.subscription_use_cases import (
    CancelSubscriptionUseCase,
    CreateSubscriptionUseCase,
    GetSubscriptionStatusUseCase,
    HandleWebhookUseCase,
    ListSubscriptionPlansUseCase,
    ListSubscriptionsUseCase,
    ProcessPaymentSuccessUseCase,
    ProcessPaymentUseCase,
    RenewSubscriptionUseCase,
    get_payment_provider,
)
from domain.business.repositories import BusinessRepository
from domain.subscription.entities import PaymentProvider
from domain.subscription.repositories import (
    PaymentTransactionRepository,
    SubscriptionPlanRepository,
    SubscriptionRepository,
)
from domain.subscription.services import SubscriptionDomainService
from infrastructure.persistence.repositories import (
    BusinessRepositoryImpl,
    PaymentTransactionRepositoryImpl,
    SubscriptionPlanRepositoryImpl,
    SubscriptionRepositoryImpl,
)
from infrastructure.webhooks.mobile_money_webhook_handler import (
    handle_mobile_money_webhook,
)
from infrastructure.webhooks.stripe_webhook_handler import handle_stripe_webhook
from presentation.serializers.business_serializers import BusinessIdQuerySerializer
from presentation.serializers.subscription_serializers import (
    PaymentInitiateSerializer,
    PaymentResponseSerializer,
    SubscriptionCancelSerializer,
    SubscriptionCreateSerializer,
    SubscriptionPlanSerializer,
    SubscriptionRenewSerializer,
    SubscriptionSerializer,
)
from shared.exceptions.specific import BadRequestError
from shared.views.base_viewset import BaseViewSet

logger = logging.getLogger(__name__)


class SubscriptionViewSet(BaseViewSet):
    """ViewSet for subscription management using DDD architecture."""

    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """Override permissions for specific actions."""
        public_actions = [
            "stripe_webhook",
            "mobile_money_webhook",
            "payment_success",
            "payment_cancel",
        ]

        if self.action in public_actions:
            return []

        if hasattr(self, "request") and self.request:
            path = self.request.path.lower()
            if any(
                action in path
                for action in [
                    "webhooks/stripe",
                    "payment/success",
                    "payment/cancel",
                    "webhooks/mobile-money",
                ]
            ):
                return []

        return super().get_permissions()

    def _get_subscription_repository(self) -> SubscriptionRepository:
        """Get subscription repository instance."""
        return SubscriptionRepositoryImpl()

    def _get_subscription_plan_repository(self) -> SubscriptionPlanRepository:
        """Get subscription plan repository instance."""
        return SubscriptionPlanRepositoryImpl()

    def _get_payment_transaction_repository(self) -> PaymentTransactionRepository:
        """Get payment transaction repository instance."""
        return PaymentTransactionRepositoryImpl()

    def _get_business_repository(self) -> BusinessRepository:
        """Get business repository instance."""
        return BusinessRepositoryImpl()

    def _get_subscription_domain_service(self) -> SubscriptionDomainService:
        """Get subscription domain service instance."""
        return SubscriptionDomainService(
            subscription_repository=self._get_subscription_repository(),
            business_repository=self._get_business_repository(),
        )

    @swagger_auto_schema(
        operation_summary="List subscription plans",
        operation_description=(
            "Get all available subscription plans. Use this endpoint to get the plan_id "
            "needed to create a subscription. Each plan has an 'id' field that you'll use "
            "as 'plan_id' when creating a subscription."
        ),
        manual_parameters=[
            openapi.Parameter(
                "active_only",
                openapi.IN_QUERY,
                description="Filter to show only active plans (default: true)",
                type=openapi.TYPE_BOOLEAN,
                required=False,
            ),
        ],
        responses={
            200: SubscriptionPlanSerializer,
            401: "Unauthorized",
            403: "Permission denied",
            404: "Business not found",
            400: "Bad Request",
            500: "Internal Server Error",
        },
        tags=["Subscriptions"],
    )
    @action(detail=False, methods=["get"], url_path="plans")
    def list_plans(self, request: Request) -> Response:
        """List all subscription plans."""
        try:
            active_only = request.query_params.get("active_only", "true").lower() == "true"
            use_case = ListSubscriptionPlansUseCase(
                plan_repository=self._get_subscription_plan_repository()
            )
            plans = use_case.execute(active_only=active_only)

            plans_data = [SubscriptionPlanSerializer.from_dto(plan) for plan in plans]

            return self.success(
                message="Subscription plans retrieved successfully",
                data=plans_data,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create subscription",
        operation_description="Create a new subscription for a business with optional trial period.",
        manual_parameters=[
            openapi.Parameter(
                "business_id",
                openapi.IN_QUERY,
                description="Business ID (required)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=True,
            ),
        ],
        request_body=SubscriptionCreateSerializer,
        responses={
            201: SubscriptionSerializer,
            400: "Bad Request",
            401: "Unauthorized",
            403: "Permission denied",
            404: "Business not found",
            500: "Internal Server Error",
        },
        tags=["Subscriptions"],
    )
    def create(self, request: Request) -> Response:
        """Create a new subscription."""
        serializer = SubscriptionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            query_serializer = BusinessIdQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]

            dto = serializer.to_dto(str(business_id))
            use_case = CreateSubscriptionUseCase(
                subscription_repository=self._get_subscription_repository(),
                plan_repository=self._get_subscription_plan_repository(),
                business_repository=self._get_business_repository(),
                subscription_domain_service=self._get_subscription_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            subscription_dto = use_case.execute(dto)

            return self.success(
                message="Subscription created successfully",
                data=SubscriptionSerializer.from_dto(subscription_dto),
                status_code=status.HTTP_201_CREATED,
            )
        except BadRequestError as e:
            return self.error(
                message=str(e.detail),
                status_code=status.HTTP_400_BAD_REQUEST,
                code=e.code,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get subscription",
        operation_description="Get subscription details by ID.",
        responses={
            200: SubscriptionSerializer,
            401: "Unauthorized",
            404: "Subscription not found",
        },
        tags=["Subscriptions"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get subscription details."""
        try:
            use_case = GetSubscriptionStatusUseCase(
                subscription_repository=self._get_subscription_repository(),
                plan_repository=self._get_subscription_plan_repository(),
                subscription_id=pk,
            )
            subscription_dto = use_case.execute()

            return self.success(
                message="Subscription retrieved successfully",
                data=SubscriptionSerializer.from_dto(subscription_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="List subscriptions",
        operation_description="List all subscriptions for a business.",
        manual_parameters=[
            openapi.Parameter(
                "business_id",
                openapi.IN_QUERY,
                description="Business ID (required)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_UUID,
                required=True,
            ),
        ],
        query_serializer=BusinessIdQuerySerializer,
        responses={
            200: SubscriptionSerializer,
            400: "Bad Request",
            401: "Unauthorized",
            403: "Permission denied",
            404: "Business not found",
            500: "Internal Server Error",
        },
        tags=["Subscriptions"],
    )
    def list(self, request: Request) -> Response:
        """List all subscriptions for a business."""
        try:
            query_serializer = BusinessIdQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]

            use_case = ListSubscriptionsUseCase(
                subscription_repository=self._get_subscription_repository(),
                plan_repository=self._get_subscription_plan_repository(),
                business_id=business_id,
            )
            subscriptions = use_case.execute()

            subscriptions_data = [SubscriptionSerializer.from_dto(sub) for sub in subscriptions]

            return self.success(
                message="Subscriptions retrieved successfully",
                data=subscriptions_data,
                status_code=status.HTTP_200_OK,
            )
        except BadRequestError as e:
            return self.error(
                message=str(e.detail),
                status_code=status.HTTP_400_BAD_REQUEST,
                code=e.code,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Initiate payment",
        operation_description="Initiate a payment for a subscription.",
        request_body=PaymentInitiateSerializer,
        responses={
            200: PaymentResponseSerializer,
            400: "Bad Request",
            401: "Unauthorized",
            404: "Subscription not found",
        },
        tags=["Subscriptions"],
    )
    @action(detail=True, methods=["post"], url_path="payments")
    def initiate_payment(self, request: Request, pk: UUID) -> Response:
        """Initiate a payment for a subscription."""
        serializer = PaymentInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto(str(pk))
            use_case = ProcessPaymentUseCase(
                subscription_repository=self._get_subscription_repository(),
                plan_repository=self._get_subscription_plan_repository(),
                transaction_repository=self._get_payment_transaction_repository(),
                subscription_id=pk,
                user_id=request.user.id,
            )
            payment_dto = use_case.execute(dto)

            return self.success(
                message="Payment initiated successfully",
                data=PaymentResponseSerializer.from_dto(payment_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Cancel subscription",
        operation_description="Cancel a subscription.",
        request_body=SubscriptionCancelSerializer,
        responses={
            200: SubscriptionSerializer,
            400: "Bad Request",
            401: "Unauthorized",
            404: "Subscription not found",
        },
        tags=["Subscriptions"],
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel_subscription(self, request: Request, pk: UUID) -> Response:
        """Cancel a subscription."""
        serializer = SubscriptionCancelSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = CancelSubscriptionUseCase(
                subscription_repository=self._get_subscription_repository(),
                business_repository=self._get_business_repository(),
                subscription_id=pk,
                user_id=request.user.id,
            )
            subscription_dto = use_case.execute(dto)

            return self.success(
                message="Subscription cancelled successfully",
                data=SubscriptionSerializer.from_dto(subscription_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Renew subscription",
        operation_description="Renew a subscription.",
        request_body=SubscriptionRenewSerializer,
        responses={
            200: SubscriptionSerializer,
            400: "Bad Request",
            401: "Unauthorized",
            404: "Subscription not found",
        },
        tags=["Subscriptions"],
    )
    @action(detail=True, methods=["post"], url_path="renew")
    def renew_subscription(self, request: Request, pk: UUID) -> Response:
        """Renew a subscription."""
        serializer = SubscriptionRenewSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = RenewSubscriptionUseCase(
                subscription_repository=self._get_subscription_repository(),
                plan_repository=self._get_subscription_plan_repository(),
                subscription_domain_service=self._get_subscription_domain_service(),
                subscription_id=pk,
                user_id=request.user.id,
            )
            subscription_dto = use_case.execute(dto)

            return self.success(
                message="Subscription renewed successfully",
                data=SubscriptionSerializer.from_dto(subscription_dto),
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Stripe webhook",
        operation_description="Handle Stripe webhook events.",
        responses={200: "Webhook processed", 400: "Bad Request"},
        tags=["Subscriptions"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="webhooks/stripe",
        permission_classes=[],
    )
    def stripe_webhook(self, request: Request) -> Response:
        """Handle Stripe webhook."""
        try:
            logger.info(f"Headers: {dict(request.headers)}")

            webhook_data = handle_stripe_webhook(request)
            if "error" in webhook_data:
                return self.error(
                    message=webhook_data["error"],
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="WEBHOOK_ERROR",
                )

            payload = webhook_data.get("payload", {})
            signature = (
                None
                if isinstance(payload, dict) and "type" in payload
                else webhook_data.get("signature")
            )

            dto = WebhookPayloadDTO(
                provider=PaymentProvider.STRIPE,
                event_type=webhook_data.get("event_type", ""),
                payload=payload,
                signature=signature,
            )

            use_case = HandleWebhookUseCase(
                subscription_repository=self._get_subscription_repository(),
                transaction_repository=self._get_payment_transaction_repository(),
                business_repository=self._get_business_repository(),
                subscription_domain_service=self._get_subscription_domain_service(),
            )
            result = use_case.execute(dto)

            return self.success(
                message="Webhook processed successfully",
                data=result,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Payment success",
        operation_description="Handle successful payment redirect from payment provider.",
        responses={200: "Payment successful", 404: "Transaction not found"},
        tags=["Subscriptions"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="payment/success",
        permission_classes=[],
    )
    def payment_success(self, request: Request) -> Response:
        """Handle payment success redirect from payment provider."""
        try:
            transaction_id_str = request.query_params.get("transaction_id")
            if not transaction_id_str:
                return self.error(
                    message="transaction_id query parameter is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_TRANSACTION_ID",
                )

            try:
                transaction_id = UUID(transaction_id_str)
            except (ValueError, TypeError):
                return self.error(
                    message="Invalid transaction_id format",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_TRANSACTION_ID",
                )

            # Get payment provider from transaction
            transaction = self._get_payment_transaction_repository().get_by_id(transaction_id)
            if not transaction:
                return self.error(
                    message="Transaction not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="TRANSACTION_NOT_FOUND",
                )

            # Get payment provider service
            payment_provider = get_payment_provider(transaction.provider)

            # Use case to process payment success
            use_case = ProcessPaymentSuccessUseCase(
                subscription_repository=self._get_subscription_repository(),
                transaction_repository=self._get_payment_transaction_repository(),
                business_repository=self._get_business_repository(),
                subscription_domain_service=self._get_subscription_domain_service(),
                payment_provider=payment_provider,
            )
            result = use_case.execute(transaction_id)

            return self.success(
                message="Payment successful",
                data=result,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Payment success handling failed: {e}", exc_info=True)
            return self.handle_exception(e)

    @action(
        detail=False,
        methods=["get"],
        url_path="payment/cancel",
        permission_classes=[],
    )
    def payment_cancel(self, request: Request) -> Response:
        """Handle payment cancellation redirect from Stripe."""
        try:
            session_id = request.query_params.get("session_id")

            return self.success(
                message="Payment was cancelled",
                data={
                    "session_id": session_id,
                    "status": "cancelled",
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Mobile Money webhook",
        operation_description="Handle Mobile Money webhook events (MTN or Orange).",
        responses={200: "Webhook processed", 400: "Bad Request"},
        tags=["Subscriptions"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="webhooks/mobile-money",
        permission_classes=[],
    )
    def mobile_money_webhook(self, request: Request) -> Response:
        """Handle Mobile Money webhook."""
        try:
            provider_param = request.query_params.get("provider", "mtn_mobile_money")
            if provider_param not in ["mtn_mobile_money", "orange_mobile_money"]:
                return self.error(
                    message="Invalid provider. Must be 'mtn_mobile_money' or 'orange_mobile_money'",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_PROVIDER",
                )

            provider = PaymentProvider(provider_param)
            webhook_data = handle_mobile_money_webhook(request, provider_param)

            if "error" in webhook_data:
                return self.error(
                    message=webhook_data["error"],
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="WEBHOOK_ERROR",
                )

            dto = WebhookPayloadDTO(
                provider=provider,
                event_type=webhook_data.get("event_type", ""),
                payload=webhook_data.get("payload", {}),
                signature=webhook_data.get("signature"),
            )

            use_case = HandleWebhookUseCase(
                subscription_repository=self._get_subscription_repository(),
                transaction_repository=self._get_payment_transaction_repository(),
                business_repository=self._get_business_repository(),
                subscription_domain_service=self._get_subscription_domain_service(),
            )
            result = use_case.execute(dto)

            return self.success(
                message="Webhook processed successfully",
                data=result,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
