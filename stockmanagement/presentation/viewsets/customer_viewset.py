"""Customer ViewSet for customer management."""

from __future__ import annotations

from uuid import UUID

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.dto.credit_dto import CreditCreateDTO, CreditPaymentCreateDTO
from application.dto.customer_list_filter_dto import CustomerListFilterDTO
from application.use_cases.credit_use_cases import (
    CreateCreditUseCase,
    GetCreditPaymentsUseCase,
    ListCreditsUseCase,
    PayCreditUseCase,
)
from application.use_cases.customer_use_cases import (
    CreateCustomerUseCase,
    DeleteCustomerUseCase,
    GetCustomerUseCase,
    ListCustomersUseCase,
    UpdateCustomerUseCase,
)
from domain.business.services import BusinessDomainService
from domain.credit.entities import CreditStatus
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    CreditPaymentRepositoryImpl,
    CreditRepositoryImpl,
    CustomerRepositoryImpl,
)
from presentation.serializers.credit_serializers import (
    CreditCreateSerializer,
    CreditPaymentCreateSerializer,
    CreditResponseSerializer,
)
from presentation.serializers.customer_serializers import (
    CustomerCreateSerializer,
    CustomerListQuerySerializer,
    CustomerResponseSerializer,
    CustomerUpdateSerializer,
)
from shared.permissions.business_permissions import IsBusinessActive
from shared.security.query_params_validator import QueryParamsValidator
from shared.views.base_viewset import BaseViewSet


class CustomerViewSet(BaseViewSet):
    """ViewSet for customer management."""

    permission_classes = [IsAuthenticated, IsBusinessActive]

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        return BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    @swagger_auto_schema(
        operation_summary="List customers",
        operation_description="Get all customers for a business.",
        query_serializer=CustomerListQuerySerializer,
        responses={
            200: CustomerResponseSerializer(many=True),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Customer"],
    )
    def list(self, request: Request) -> Response:
        """List all customers for a business."""
        try:
            # Validate query parameters
            query_serializer = CustomerListQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]

            filter_payload = self.parse_list_filters(
                request,
                search_fields=["name", "email", "phone_number"],
                order_fields=[
                    "name",
                    "created_at",
                    "total_purchases",
                    "loyalty_points",
                ],
                filter_definitions={
                    "name": {"type": "string", "max_length": 255},
                    "customer_type": {
                        "type": "enum",
                        "choices": ["REGULAR", "WHOLESALER"],
                    },
                },
                additional_allowed_params=["business_id"],
            )
            filter_payload["filters"]["business_id"] = business_id
            filter_dto = CustomerListFilterDTO.from_payload(filter_payload)

            use_case = ListCustomersUseCase(
                customer_repository=CustomerRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                limit=QueryParamsValidator.MAX_PAGE_SIZE,
            )
            customers = use_case.execute()

            if filter_dto.customer_type:
                customers = [
                    customer
                    for customer in customers
                    if customer.customer_type == filter_dto.customer_type
                ]

            customers = self.apply_filtering_to_items(
                customers,
                filter_payload,
                name_fields=["name"],
            )

            return self.paginated_response(
                request=request,
                queryset=customers,
                serializer_class=CustomerResponseSerializer,
                message="Customers retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create customer",
        operation_description="Create a new customer for a business. business_id must be provided in the request body.",
        request_body=CustomerCreateSerializer,
        responses={
            201: CustomerResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Customer"],
    )
    def create(self, request: Request) -> Response:
        """Create a new customer."""
        serializer = CustomerCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            # Get business_id from serializer validated data
            business_id_str = serializer.validated_data.get("business_id")
            if not business_id_str:
                return self.error(
                    message="business_id is required in request body",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_BUSINESS_ID",
                )

            try:
                business_id = UUID(str(business_id_str))
            except (ValueError, TypeError):
                return self.error(
                    message="Invalid business_id format",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_BUSINESS_ID",
                )

            dto = serializer.to_dto()
            use_case = CreateCustomerUseCase(
                customer_repository=CustomerRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            customer_dto = use_case.execute(dto)

            return self.success(
                message="Customer created successfully",
                data={
                    "id": str(customer_dto.id),
                    "business_id": (
                        str(customer_dto.business_id)
                        if customer_dto.business_id
                        else None
                    ),
                    "name": customer_dto.name,
                    "email": customer_dto.email,
                    "phone_number": customer_dto.phone_number,
                    "address": customer_dto.address,
                    "customer_type": customer_dto.customer_type,
                    "loyalty_points": str(customer_dto.loyalty_points),
                    "total_purchases": str(customer_dto.total_purchases),
                    "created_at": customer_dto.created_at.isoformat(),
                    "updated_at": customer_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get customer",
        operation_description="Get customer details by ID. business_id is retrieved from the customer.",
        responses={
            200: CustomerResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Customer not found",
        },
        tags=["Customer"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get customer by ID."""
        try:
            # Get customer first to retrieve business_id
            customer_repo = CustomerRepositoryImpl()
            customer = customer_repo.get_by_id(pk)
            if not customer:
                return self.error(
                    message="Customer not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="CUSTOMER_NOT_FOUND",
                )

            if not customer.business_id:
                return self.error(
                    message="Customer has no associated business",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="NO_BUSINESS_ID",
                )

            use_case = GetCustomerUseCase(
                customer_repository=customer_repo,
                business_domain_service=self._get_business_domain_service(),
                customer_id=pk,
                business_id=customer.business_id,
                user_id=request.user.id,
            )
            customer_dto = use_case.execute()

            return self.success(
                message="Customer retrieved successfully",
                data={
                    "id": str(customer_dto.id),
                    "business_id": (
                        str(customer_dto.business_id)
                        if customer_dto.business_id
                        else None
                    ),
                    "name": customer_dto.name,
                    "email": customer_dto.email,
                    "phone_number": customer_dto.phone_number,
                    "address": customer_dto.address,
                    "customer_type": customer_dto.customer_type,
                    "loyalty_points": str(customer_dto.loyalty_points),
                    "total_purchases": str(customer_dto.total_purchases),
                    "created_at": customer_dto.created_at.isoformat(),
                    "updated_at": customer_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update customer",
        operation_description="Update customer details. business_id is retrieved from the customer.",
        request_body=CustomerUpdateSerializer,
        responses={
            200: CustomerResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Customer not found",
        },
        tags=["Customer"],
    )
    def update(self, request: Request, pk: UUID) -> Response:
        """Update customer."""
        # Get customer first to retrieve business_id
        customer_repo = CustomerRepositoryImpl()
        customer = customer_repo.get_by_id(pk)
        if not customer:
            return self.error(
                message="Customer not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="CUSTOMER_NOT_FOUND",
            )

        if not customer.business_id:
            return self.error(
                message="Customer has no associated business",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="NO_BUSINESS_ID",
            )

        serializer = CustomerUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = UpdateCustomerUseCase(
                customer_repository=customer_repo,
                business_domain_service=self._get_business_domain_service(),
                customer_id=pk,
                business_id=customer.business_id,
                user_id=request.user.id,
            )
            customer_dto = use_case.execute(dto)

            return self.success(
                message="Customer updated successfully",
                data={
                    "id": str(customer_dto.id),
                    "name": customer_dto.name,
                    "email": customer_dto.email,
                    "phone_number": customer_dto.phone_number,
                    "address": customer_dto.address,
                    "customer_type": customer_dto.customer_type,
                    "loyalty_points": str(customer_dto.loyalty_points),
                    "total_purchases": str(customer_dto.total_purchases),
                    "updated_at": customer_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete customer",
        operation_description="Delete a customer. business_id is retrieved from the customer.",
        responses={
            204: "No Content",
            400: "Bad Request",
            403: "Permission denied",
            404: "Customer not found",
        },
        tags=["Customer"],
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        """Delete customer."""
        try:
            # Get customer first to retrieve business_id
            customer_repo = CustomerRepositoryImpl()
            customer = customer_repo.get_by_id(pk)
            if not customer:
                return self.error(
                    message="Customer not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="CUSTOMER_NOT_FOUND",
                )

            if not customer.business_id:
                return self.error(
                    message="Customer has no associated business",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="NO_BUSINESS_ID",
                )

            use_case = DeleteCustomerUseCase(
                customer_repository=customer_repo,
                business_domain_service=self._get_business_domain_service(),
                customer_id=pk,
                business_id=customer.business_id,
                user_id=request.user.id,
            )
            use_case.execute()

            return self.success(
                message="Customer deleted successfully",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create credit for customer",
        operation_description="Create a credit for a customer.",
        request_body=CreditCreateSerializer,
        responses={
            201: CreditResponseSerializer,
            400: "Bad request",
            403: "Permission denied",
        },
        tags=["Customer"],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="credit",
    )
    def create_credit(self, request: Request, pk: UUID) -> Response:
        """Create a credit for a customer."""
        try:
            serializer = CreditCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Get customer to find business_id
            customer = CustomerRepositoryImpl().get_by_id(pk)
            if not customer:
                return self.error(
                    message="Customer not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="CUSTOMER_NOT_FOUND",
                )

            # Check if user has access to business
            if not self._get_business_domain_service().user_has_access(
                customer.business_id, request.user.id
            ):
                return self.error(
                    message="You don't have access to this business",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            dto = CreditCreateDTO(
                customer_id=pk,
                invoice_id=serializer.validated_data.get("invoice_id"),
                amount=serializer.validated_data["amount"],
                due_date=serializer.validated_data["due_date"],
                notes=serializer.validated_data.get("notes"),
            )

            use_case = CreateCreditUseCase(
                credit_repository=CreditRepositoryImpl(),
                business_id=customer.business_id,
                user_id=request.user.id,
            )
            credit_dto = use_case.execute(dto)

            return self.success(
                message="Credit created successfully",
                data={
                    "id": str(credit_dto.id),
                    "business_id": str(credit_dto.business_id),
                    "customer_id": str(credit_dto.customer_id),
                    "invoice_id": (
                        str(credit_dto.invoice_id) if credit_dto.invoice_id else None
                    ),
                    "amount": str(credit_dto.amount),
                    "paid_amount": str(credit_dto.paid_amount),
                    "remaining_amount": str(credit_dto.remaining_amount),
                    "due_date": credit_dto.due_date.isoformat(),
                    "status": credit_dto.status,
                    "notes": credit_dto.notes,
                    "is_overdue": credit_dto.is_overdue,
                    "created_at": credit_dto.created_at.isoformat(),
                    "updated_at": credit_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="List customer credits",
        operation_description="Get all credits for a customer.",
        responses={200: "List of credits", 403: "Permission denied"},
        tags=["Customer"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="credit",
    )
    def list_credits(self, request: Request, pk: UUID) -> Response:
        """List all credits for a customer."""
        try:
            # Get customer to find business_id
            customer = CustomerRepositoryImpl().get_by_id(pk)
            if not customer:
                return self.error(
                    message="Customer not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="CUSTOMER_NOT_FOUND",
                )

            # Check if user has access to business
            if not self._get_business_domain_service().user_has_access(
                customer.business_id, request.user.id
            ):
                return self.error(
                    message="You don't have access to this business",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            # Get and validate status filter if provided
            status_param = QueryParamsValidator.validate_enum(
                request.query_params.get("status"),
                allowed_values=["PENDING", "PARTIAL", "PAID", "OVERDUE", "CANCELLED"],
                param_name="status",
            )
            status_filter = CreditStatus(status_param) if status_param else None

            overdue_only = QueryParamsValidator.validate_boolean(
                request.query_params.get("overdue_only", "false"),
                param_name="overdue_only",
            )

            use_case = ListCreditsUseCase(
                credit_repository=CreditRepositoryImpl(),
                business_id=customer.business_id,
                customer_id=pk,
                status=status_filter,
                overdue_only=overdue_only,
            )
            credits = use_case.execute()

            return self.success(
                message="Credits retrieved successfully",
                data=[
                    {
                        "id": str(c.id),
                        "business_id": str(c.business_id),
                        "customer_id": str(c.customer_id),
                        "invoice_id": str(c.invoice_id) if c.invoice_id else None,
                        "amount": str(c.amount),
                        "paid_amount": str(c.paid_amount),
                        "remaining_amount": str(c.remaining_amount),
                        "due_date": c.due_date.isoformat(),
                        "status": c.status,
                        "notes": c.notes,
                        "is_overdue": c.is_overdue,
                        "created_at": c.created_at.isoformat(),
                        "updated_at": c.updated_at.isoformat(),
                    }
                    for c in credits
                ],
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Pay credit",
        operation_description="Make a payment towards a credit.",
        request_body=CreditPaymentCreateSerializer,
        responses={
            200: "Payment successful",
            400: "Bad request",
            404: "Credit not found",
        },
        tags=["Customer"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="credit/(?P<credit_id>[^/.]+)/pay",
    )
    def pay_credit(self, request: Request, credit_id: UUID) -> Response:
        """Pay a credit."""
        try:
            serializer = CreditPaymentCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            # Get credit to find business_id
            credit = CreditRepositoryImpl().get_by_id(credit_id)
            if not credit:
                return self.error(
                    message="Credit not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="CREDIT_NOT_FOUND",
                )

            # Check if user has access to business
            if not self._get_business_domain_service().user_has_access(
                credit.business_id, request.user.id
            ):
                return self.error(
                    message="You don't have access to this business",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            dto = CreditPaymentCreateDTO(
                amount=serializer.validated_data["amount"],
                payment_method=serializer.validated_data.get("payment_method", "cash"),
                notes=serializer.validated_data.get("notes"),
                payment_date=serializer.validated_data.get("payment_date"),
            )

            use_case = PayCreditUseCase(
                credit_repository=CreditRepositoryImpl(),
                credit_payment_repository=CreditPaymentRepositoryImpl(),
                credit_id=credit_id,
                user_id=request.user.id,
            )
            credit_dto, payment_dto = use_case.execute(dto)

            return self.success(
                message="Credit payment processed successfully",
                data={
                    "credit": {
                        "id": str(credit_dto.id),
                        "remaining_amount": str(credit_dto.remaining_amount),
                        "paid_amount": str(credit_dto.paid_amount),
                        "status": credit_dto.status,
                    },
                    "payment": {
                        "id": str(payment_dto.id),
                        "amount": str(payment_dto.amount),
                        "payment_date": payment_dto.payment_date.isoformat(),
                        "payment_method": payment_dto.payment_method,
                    },
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get credit payment history",
        operation_description="Get payment history for a credit.",
        responses={200: "List of payments", 404: "Credit not found"},
        tags=["Customer"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="credit/(?P<credit_id>[^/.]+)/payments",
    )
    def get_credit_payments(self, request: Request, credit_id: UUID) -> Response:
        """Get payment history for a credit."""
        try:
            # Get credit to verify access
            credit = CreditRepositoryImpl().get_by_id(credit_id)
            if not credit:
                return self.error(
                    message="Credit not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="CREDIT_NOT_FOUND",
                )

            # Check if user has access to business
            if not self._get_business_domain_service().user_has_access(
                credit.business_id, request.user.id
            ):
                return self.error(
                    message="You don't have access to this business",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            use_case = GetCreditPaymentsUseCase(
                credit_payment_repository=CreditPaymentRepositoryImpl(),
                credit_id=credit_id,
            )
            payments = use_case.execute()

            return self.success(
                message="Credit payments retrieved successfully",
                data=[
                    {
                        "id": str(p.id),
                        "credit_id": str(p.credit_id),
                        "amount": str(p.amount),
                        "payment_date": p.payment_date.isoformat(),
                        "payment_method": p.payment_method,
                        "notes": p.notes,
                        "created_at": p.created_at.isoformat(),
                    }
                    for p in payments
                ],
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
