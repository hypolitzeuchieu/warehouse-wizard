"""Subscription ViewSet using DDD architecture with use cases."""

from __future__ import annotations

from uuid import UUID

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
    ProcessPaymentUseCase,
    RenewSubscriptionUseCase,
)
from domain.subscription.entities import PaymentProvider
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
from presentation.serializers.response_serializers import (
    get_error_response_schema,
    get_list_response_schema,
    get_success_response_schema_with_data,
)
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
from shared.views.business_id_mixin import BusinessIdMixin


class SubscriptionViewSet(BaseViewSet, BusinessIdMixin):
    """ViewSet for subscription management using DDD architecture."""

    permission_classes = [IsAuthenticated]

    def _get_subscription_domain_service(self) -> SubscriptionDomainService:
        """Get subscription domain service instance."""
        return SubscriptionDomainService(
            subscription_repository=SubscriptionRepositoryImpl(),
            business_repository=BusinessRepositoryImpl(),
        )

    @swagger_auto_schema(
        operation_summary="List subscription plans",
        operation_description="Get all available subscription plans.",
        responses={
            200: get_list_response_schema(SubscriptionPlanSerializer),
            401: get_error_response_schema(),
        },
        tags=["Subscriptions"],
    )
    @action(detail=False, methods=["get"], url_path="plans")
    def list_plans(self, request: Request) -> Response:
        """List all subscription plans."""
        try:
            active_only = (
                request.query_params.get("active_only", "true").lower() == "true"
            )
            use_case = ListSubscriptionPlansUseCase(
                plan_repository=SubscriptionPlanRepositoryImpl()
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
        request_body=SubscriptionCreateSerializer,
        responses={
            201: get_success_response_schema_with_data(SubscriptionSerializer),
            400: get_error_response_schema(),
            401: get_error_response_schema(),
            403: get_error_response_schema(),
            404: get_error_response_schema(),
        },
        tags=["Subscriptions"],
    )
    def create(self, request: Request) -> Response:
        """Create a new subscription."""
        serializer = SubscriptionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            business_id = self._get_business_id_from_query(request)
            dto = serializer.to_dto(str(business_id))
            use_case = CreateSubscriptionUseCase(
                subscription_repository=SubscriptionRepositoryImpl(),
                plan_repository=SubscriptionPlanRepositoryImpl(),
                business_repository=BusinessRepositoryImpl(),
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
            200: get_success_response_schema_with_data(SubscriptionSerializer),
            401: get_error_response_schema(),
            404: get_error_response_schema(),
        },
        tags=["Subscriptions"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get subscription details."""
        try:
            use_case = GetSubscriptionStatusUseCase(
                subscription_repository=SubscriptionRepositoryImpl(),
                plan_repository=SubscriptionPlanRepositoryImpl(),
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
        responses={
            200: get_list_response_schema(SubscriptionSerializer),
            400: get_error_response_schema(),
            401: get_error_response_schema(),
        },
        tags=["Subscriptions"],
    )
    def list(self, request: Request) -> Response:
        """List all subscriptions for a business."""
        try:
            business_id = self._get_business_id_from_query(request)
            use_case = ListSubscriptionsUseCase(
                subscription_repository=SubscriptionRepositoryImpl(),
                plan_repository=SubscriptionPlanRepositoryImpl(),
                business_id=business_id,
            )
            subscriptions = use_case.execute()

            subscriptions_data = [
                SubscriptionSerializer.from_dto(sub) for sub in subscriptions
            ]

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
            200: get_success_response_schema_with_data(PaymentResponseSerializer),
            400: get_error_response_schema(),
            401: get_error_response_schema(),
            404: get_error_response_schema(),
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
                subscription_repository=SubscriptionRepositoryImpl(),
                plan_repository=SubscriptionPlanRepositoryImpl(),
                transaction_repository=PaymentTransactionRepositoryImpl(),
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
            200: get_success_response_schema_with_data(SubscriptionSerializer),
            400: get_error_response_schema(),
            401: get_error_response_schema(),
            404: get_error_response_schema(),
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
                subscription_repository=SubscriptionRepositoryImpl(),
                business_repository=BusinessRepositoryImpl(),
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
            200: get_success_response_schema_with_data(SubscriptionSerializer),
            400: get_error_response_schema(),
            401: get_error_response_schema(),
            404: get_error_response_schema(),
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
                subscription_repository=SubscriptionRepositoryImpl(),
                plan_repository=SubscriptionPlanRepositoryImpl(),
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
        responses={
            200: get_success_response_schema_with_data(None),
            400: get_error_response_schema(),
        },
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
            webhook_data = handle_stripe_webhook(request)
            if "error" in webhook_data:
                return self.error(
                    message=webhook_data["error"],
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="WEBHOOK_ERROR",
                )

            dto = WebhookPayloadDTO(
                provider=PaymentProvider.STRIPE,
                event_type=webhook_data.get("event_type", ""),
                payload=webhook_data.get("payload", {}),
                signature=webhook_data.get("signature"),
            )

            use_case = HandleWebhookUseCase(
                subscription_repository=SubscriptionRepositoryImpl(),
                transaction_repository=PaymentTransactionRepositoryImpl(),
                business_repository=BusinessRepositoryImpl(),
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
        operation_summary="Mobile Money webhook",
        operation_description="Handle Mobile Money webhook events (MTN or Orange).",
        responses={
            200: get_success_response_schema_with_data(None),
            400: get_error_response_schema(),
        },
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
                subscription_repository=SubscriptionRepositoryImpl(),
                transaction_repository=PaymentTransactionRepositoryImpl(),
                business_repository=BusinessRepositoryImpl(),
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
