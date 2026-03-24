"""Finance ViewSet for expenses and financial management."""

from __future__ import annotations

from uuid import UUID

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.dto.expense_list_filter_dto import ExpenseListFilterDTO
from application.use_cases.credit_use_cases import CheckOverdueCreditsUseCase
from application.use_cases.finance_use_cases import (
    CreateExpenseUseCase,
    DeleteExpenseUseCase,
    GetExpenseUseCase,
    ListExpensesUseCase,
    UpdateExpenseUseCase,
)
from application.use_cases.salary_use_cases import (
    CreateSalaryUseCase,
    GetSalaryHistoryUseCase,
    GetSalaryUseCase,
    PromoteEmployeeUseCase,
    UpdateSalaryUseCase,
)
from domain.business.services import BusinessDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    CreditRepositoryImpl,
    ExpenseAuditLogRepositoryImpl,
    ExpenseRepositoryImpl,
    SalaryRepositoryImpl,
    UserRepositoryImpl,
)
from presentation.serializers.finance_serializers import (
    ExpenseCreateSerializer,
    ExpenseListQuerySerializer,
    ExpenseResponseSerializer,
    ExpenseUpdateSerializer,
    SalaryCreateSerializer,
    SalaryPromotionSerializer,
    SalaryResponseSerializer,
    SalaryUpdateSerializer,
)
from shared.security.query_params_validator import QueryParamsValidator
from shared.views.base_viewset import BaseViewSet


class FinanceViewSet(BaseViewSet):
    """ViewSet for finance management (expenses, salaries, payroll)."""

    permission_classes = [IsAuthenticated]

    def _get_business_domain_service(self) -> BusinessDomainService:
        """Get business domain service instance."""
        return BusinessDomainService(
            business_repository=BusinessRepositoryImpl(),
            business_member_repository=BusinessMemberRepositoryImpl(),
        )

    def _resolve_user_name(self, user_id: UUID | None) -> str | None:
        """Resolve user name from repository with caching."""
        if not user_id:
            return None
        if not hasattr(self, "_expense_user_cache"):
            self._expense_user_cache = {}
        cache: dict[UUID, str | None] = self._expense_user_cache
        if user_id in cache:
            return cache[user_id]
        if not hasattr(self, "_expense_user_repo"):
            self._expense_user_repo = UserRepositoryImpl()
        user_repo: UserRepositoryImpl = self._expense_user_repo
        user = user_repo.get_by_id(user_id)
        name = None
        if user:
            name = (
                getattr(user, "full_name", None)
                or getattr(user, "name", None)
                or getattr(user, "email", None)
            )
        cache[user_id] = name
        return name

    def _attach_expense_user_names(self, expenses) -> None:
        """Attach user_name to expense DTOs."""
        if isinstance(expenses, list):
            for dto in expenses:
                dto.user_name = self._resolve_user_name(dto.user_id)
        else:
            expenses.user_name = self._resolve_user_name(expenses.user_id)

    @swagger_auto_schema(
        operation_summary="List expenses",
        operation_description="Get all expenses for a business with optional filters.",
        query_serializer=ExpenseListQuerySerializer,
        responses={
            200: ExpenseResponseSerializer(many=True),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Finance"],
    )
    def list(self, request: Request) -> Response:
        """List all expenses for a business."""
        try:
            # Validate query parameters
            query_serializer = ExpenseListQuerySerializer(data=request.query_params)
            if not query_serializer.is_valid():
                return self.handle_validation_error(query_serializer)

            business_id = query_serializer.validated_data["business_id"]

            filter_payload = self.parse_list_filters(
                request,
                search_fields=["reason"],
                order_fields=["created_at", "updated_at", "amount"],
                filter_definitions={
                    "expense_type": {
                        "type": "enum",
                        "choices": [
                            "REPLENISHMENT",
                            "MISCELLANEOUS",
                            "ELECTRICITY",
                            "WATER",
                            "SALARY",
                            "EXTRA",
                            "MAINTENANCE",
                            "TAX",
                            "RENT",
                            "MARKETING",
                            "INSURANCE",
                            "TRANSPORT",
                            "UTILITIES",
                            "OFFICE_SUPPLIES",
                            "PROFESSIONAL_SERVICES",
                        ],
                    },
                    "start_date": {"type": "date"},
                    "end_date": {"type": "date"},
                    "payment_method": {
                        "type": "enum",
                        "choices": [
                            "CASH",
                            "MOBILE_MONEY",
                            "BANK_TRANSFER",
                            "CARD",
                            "CHECK",
                            "OTHER",
                        ],
                    },
                    "payee_type": {
                        "type": "enum",
                        "choices": [
                            "EMPLOYEE",
                            "SUPPLIER",
                            "SERVICE_PROVIDER",
                            "GOVERNMENT",
                            "LANDLORD",
                            "OTHER",
                        ],
                    },
                    "min_amount": {"type": "decimal"},
                    "max_amount": {"type": "decimal"},
                    "is_approved": {"type": "boolean"},
                },
                additional_allowed_params=[
                    "business_id",
                    "payment_method",
                    "payee_type",
                    "min_amount",
                    "max_amount",
                    "is_approved",
                ],
            )
            filter_payload["filters"]["business_id"] = business_id
            optional_filters = [
                "payment_method",
                "payee_type",
                "min_amount",
                "max_amount",
                "is_approved",
            ]
            for field in optional_filters:
                value = query_serializer.validated_data.get(field)
                if value is not None:
                    filter_payload["filters"][field] = value
            filter_dto = ExpenseListFilterDTO.from_payload(filter_payload)

            expense_repo = ExpenseRepositoryImpl()
            use_case = ListExpensesUseCase(
                expense_repository=expense_repo,
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                expense_type=filter_dto.expense_type,
                start_date=filter_dto.start_date,
                end_date=filter_dto.end_date,
                payment_method=filter_dto.payment_method,
                payee_type=filter_dto.payee_type,
                min_amount=filter_dto.min_amount,
                max_amount=filter_dto.max_amount,
                is_approved=filter_dto.is_approved,
                limit=QueryParamsValidator.MAX_PAGE_SIZE,
            )
            expenses = use_case.execute()

            self._attach_expense_user_names(expenses)

            expenses = self.apply_filtering_to_items(
                expenses,
                filter_payload,
                name_fields=["reason"],
            )

            return self.paginated_response(
                request=request,
                queryset=expenses,
                serializer_class=ExpenseResponseSerializer,
                message="Expenses retrieved successfully",
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Create expense",
        operation_description="Create a new expense for a business. business_id must be provided in the request body.",
        request_body=ExpenseCreateSerializer,
        responses={
            201: ExpenseResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Finance"],
    )
    def create(self, request: Request) -> Response:
        """Create a new expense."""
        serializer = ExpenseCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            business_id = serializer.validated_data["business_id"]

            dto = serializer.to_dto()
            use_case = CreateExpenseUseCase(
                expense_repository=ExpenseRepositoryImpl(),
                audit_log_repository=ExpenseAuditLogRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            expense_dto = use_case.execute(dto)
            self._attach_expense_user_names(expense_dto)

            response_payload = ExpenseResponseSerializer.from_dto(expense_dto)
            return self.success(
                message="Expense created successfully",
                data=response_payload,
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get expense",
        operation_description="Get expense details by ID. business_id is retrieved from the expense.",
        responses={
            200: ExpenseResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Expense not found",
        },
        tags=["Finance"],
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        """Get expense by ID."""
        try:
            # Get expense first to retrieve business_id
            expense_repo = ExpenseRepositoryImpl()
            expense = expense_repo.get_by_id(pk)
            if not expense:
                return self.error(
                    message="Expense not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="EXPENSE_NOT_FOUND",
                )

            use_case = GetExpenseUseCase(
                expense_repository=expense_repo,
                business_domain_service=self._get_business_domain_service(),
                expense_id=pk,
                business_id=expense.business_id,
                user_id=request.user.id,
            )
            expense_dto = use_case.execute()
            self._attach_expense_user_names(expense_dto)

            response_payload = ExpenseResponseSerializer.from_dto(expense_dto)
            return self.success(
                message="Expense retrieved successfully",
                data=response_payload,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update expense",
        operation_description="Update expense details. Only owner/manager can approve. business_id is retrieved from the expense.",
        request_body=ExpenseUpdateSerializer,
        responses={
            200: ExpenseResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Expense not found",
        },
        tags=["Finance"],
    )
    def update(self, request: Request, pk: UUID) -> Response:
        """Update expense."""
        # Get expense first to retrieve business_id
        expense_repo = ExpenseRepositoryImpl()
        expense = expense_repo.get_by_id(pk)
        if not expense:
            return self.error(
                message="Expense not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="EXPENSE_NOT_FOUND",
            )

        serializer = ExpenseUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = UpdateExpenseUseCase(
                expense_repository=expense_repo,
                audit_log_repository=ExpenseAuditLogRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                expense_id=pk,
                business_id=expense.business_id,
                user_id=request.user.id,
            )
            expense_dto = use_case.execute(dto)
            self._attach_expense_user_names(expense_dto)

            response_payload = ExpenseResponseSerializer.from_dto(expense_dto)
            return self.success(
                message="Expense updated successfully",
                data=response_payload,
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete expense",
        operation_description="Delete an expense. business_id is retrieved from the expense.",
        responses={
            204: "No Content",
            400: "Bad Request",
            403: "Permission denied",
            404: "Expense not found",
        },
        tags=["Finance"],
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        """Delete expense."""
        try:
            # Get expense first to retrieve business_id
            expense_repo = ExpenseRepositoryImpl()
            expense = expense_repo.get_by_id(pk)
            if not expense:
                return self.error(
                    message="Expense not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="EXPENSE_NOT_FOUND",
                )

            use_case = DeleteExpenseUseCase(
                expense_repository=expense_repo,
                audit_log_repository=ExpenseAuditLogRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                expense_id=pk,
                business_id=expense.business_id,
                user_id=request.user.id,
            )
            use_case.execute()

            return self.success(
                message="Expense deleted successfully",
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get overdue credits",
        operation_description="Get all overdue credits for a business and create notifications. business_id is required as query parameter.",
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
        responses={200: "List of overdue credits", 403: "Permission denied"},
        tags=["Finance"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="credits/overdue",
    )
    def get_overdue_credits(self, request: Request) -> Response:
        """Get overdue credits for a business."""
        try:
            business_id_str = request.query_params.get("business_id")
            if not business_id_str:
                return self.error(
                    message="business_id query parameter is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_BUSINESS_ID",
                )

            try:
                business_id = UUID(business_id_str)
            except (ValueError, TypeError):
                return self.error(
                    message="Invalid business_id format",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_BUSINESS_ID",
                )

            # Check if user has access to business
            if not self._get_business_domain_service().user_has_access(
                business_id, request.user.id
            ):
                return self.error(
                    message="You don't have access to this business",
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="PERMISSION_DENIED",
                )

            use_case = CheckOverdueCreditsUseCase(
                credit_repository=CreditRepositoryImpl(),
                business_id=business_id,
            )
            credits = use_case.execute()

            return self.success(
                message="Overdue credits retrieved successfully",
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
        operation_summary="Create salary",
        operation_description="Create a new salary for an employee. business_id must be provided in the request body.",
        request_body=SalaryCreateSerializer,
        responses={
            201: SalaryResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Finance"],
    )
    @action(detail=False, methods=["post"], url_path="salaries")
    def create_salary(self, request: Request) -> Response:
        """Create a new salary for an employee."""
        serializer = SalaryCreateSerializer(data=request.data)
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
            use_case = CreateSalaryUseCase(
                salary_repository=SalaryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            salary_dto = use_case.execute(dto)

            return self.success(
                message="Salary created successfully",
                data={
                    "id": str(salary_dto.id),
                    "business_id": str(salary_dto.business_id),
                    "user_id": str(salary_dto.user_id),
                    "amount": str(salary_dto.amount),
                    "currency": salary_dto.currency,
                    "payment_frequency": salary_dto.payment_frequency,
                    "deductions": str(salary_dto.deductions),
                    "bonuses": str(salary_dto.bonuses),
                    "net_salary": str(salary_dto.net_salary),
                    "effective_from": salary_dto.effective_from.isoformat(),
                    "effective_to": (
                        salary_dto.effective_to.isoformat() if salary_dto.effective_to else None
                    ),
                    "is_active": salary_dto.is_active,
                    "created_at": salary_dto.created_at.isoformat(),
                    "updated_at": salary_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get salary",
        operation_description="Get salary details by ID. business_id is retrieved from the salary.",
        responses={
            200: SalaryResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Salary not found",
        },
        tags=["Finance"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="salaries/(?P<salary_id>[^/.]+)",
    )
    def get_salary(self, request: Request, salary_id: UUID) -> Response:
        """Get salary by ID."""
        try:
            # Get salary first to retrieve business_id
            salary_repo = SalaryRepositoryImpl()
            salary = salary_repo.get_by_id(salary_id)
            if not salary:
                return self.error(
                    message="Salary not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="SALARY_NOT_FOUND",
                )

            use_case = GetSalaryUseCase(
                salary_repository=salary_repo,
                business_domain_service=self._get_business_domain_service(),
                salary_id=salary_id,
                business_id=salary.business_id,
                user_id=request.user.id,
            )
            salary_dto = use_case.execute()

            return self.success(
                message="Salary retrieved successfully",
                data={
                    "id": str(salary_dto.id),
                    "business_id": str(salary_dto.business_id),
                    "user_id": str(salary_dto.user_id),
                    "amount": str(salary_dto.amount),
                    "currency": salary_dto.currency,
                    "payment_frequency": salary_dto.payment_frequency,
                    "deductions": str(salary_dto.deductions),
                    "bonuses": str(salary_dto.bonuses),
                    "net_salary": str(salary_dto.net_salary),
                    "effective_from": salary_dto.effective_from.isoformat(),
                    "effective_to": (
                        salary_dto.effective_to.isoformat() if salary_dto.effective_to else None
                    ),
                    "is_active": salary_dto.is_active,
                    "created_at": salary_dto.created_at.isoformat(),
                    "updated_at": salary_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get salary history",
        operation_description="Get salary history for a user. Users can only see their own history unless they're owner/manager. business_id is required as query parameter.",
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
        responses={
            200: SalaryResponseSerializer(many=True),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Finance"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="salaries/user/(?P<user_id>[^/.]+)/history",
    )
    def get_salary_history(self, request: Request, user_id: UUID) -> Response:
        """Get salary history for a user."""
        try:
            business_id_str = request.query_params.get("business_id")
            if not business_id_str:
                return self.error(
                    message="business_id query parameter is required",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="MISSING_BUSINESS_ID",
                )

            try:
                business_id = UUID(business_id_str)
            except (ValueError, TypeError):
                return self.error(
                    message="Invalid business_id format",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_BUSINESS_ID",
                )

            use_case = GetSalaryHistoryUseCase(
                salary_repository=SalaryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                user_id=user_id,
                business_id=business_id,
                requester_id=request.user.id,
            )
            salaries = use_case.execute()

            return self.success(
                message="Salary history retrieved successfully",
                data=[
                    {
                        "id": str(s.id),
                        "business_id": str(s.business_id),
                        "user_id": str(s.user_id),
                        "amount": str(s.amount),
                        "currency": s.currency,
                        "payment_frequency": s.payment_frequency,
                        "deductions": str(s.deductions),
                        "bonuses": str(s.bonuses),
                        "net_salary": str(s.net_salary),
                        "effective_from": s.effective_from.isoformat(),
                        "effective_to": s.effective_to.isoformat() if s.effective_to else None,
                        "is_active": s.is_active,
                        "created_at": s.created_at.isoformat(),
                        "updated_at": s.updated_at.isoformat(),
                    }
                    for s in salaries
                ],
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Promote employee",
        operation_description="Promote an employee by creating a new salary with higher amount. business_id must be provided in the request body.",
        request_body=SalaryPromotionSerializer,
        responses={
            201: SalaryResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
        },
        tags=["Finance"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="salaries/employee/(?P<employee_id>[^/.]+)/promote",
    )
    def promote_employee(self, request: Request, employee_id: UUID) -> Response:
        """Promote an employee (create new salary with higher amount)."""
        serializer = SalaryPromotionSerializer(data=request.data)
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
            use_case = PromoteEmployeeUseCase(
                salary_repository=SalaryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                employee_id=employee_id,
                user_id=request.user.id,
            )
            salary_dto = use_case.execute(dto)

            return self.success(
                message="Employee promoted successfully",
                data={
                    "id": str(salary_dto.id),
                    "business_id": str(salary_dto.business_id),
                    "user_id": str(salary_dto.user_id),
                    "amount": str(salary_dto.amount),
                    "currency": salary_dto.currency,
                    "payment_frequency": salary_dto.payment_frequency,
                    "deductions": str(salary_dto.deductions),
                    "bonuses": str(salary_dto.bonuses),
                    "net_salary": str(salary_dto.net_salary),
                    "effective_from": salary_dto.effective_from.isoformat(),
                    "effective_to": (
                        salary_dto.effective_to.isoformat() if salary_dto.effective_to else None
                    ),
                    "is_active": salary_dto.is_active,
                    "created_at": salary_dto.created_at.isoformat(),
                    "updated_at": salary_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update salary",
        operation_description="Update salary details. Only owner/manager can update. business_id is retrieved from the salary.",
        request_body=SalaryUpdateSerializer,
        responses={
            200: SalaryResponseSerializer(),
            400: "Bad Request",
            403: "Permission denied",
            404: "Salary not found",
        },
        tags=["Finance"],
    )
    @action(
        detail=False,
        methods=["put"],
        url_path="salaries/(?P<salary_id>[^/.]+)",
    )
    def update_salary(self, request: Request, salary_id: UUID) -> Response:
        """Update salary."""
        # Get salary first to retrieve business_id
        salary_repo = SalaryRepositoryImpl()
        salary = salary_repo.get_by_id(salary_id)
        if not salary:
            return self.error(
                message="Salary not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="SALARY_NOT_FOUND",
            )

        serializer = SalaryUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = UpdateSalaryUseCase(
                salary_repository=salary_repo,
                business_domain_service=self._get_business_domain_service(),
                salary_id=salary_id,
                business_id=salary.business_id,
                user_id=request.user.id,
            )
            salary_dto = use_case.execute(dto)

            return self.success(
                message="Salary updated successfully",
                data={
                    "id": str(salary_dto.id),
                    "amount": str(salary_dto.amount),
                    "currency": salary_dto.currency,
                    "payment_frequency": salary_dto.payment_frequency,
                    "deductions": str(salary_dto.deductions),
                    "bonuses": str(salary_dto.bonuses),
                    "net_salary": str(salary_dto.net_salary),
                    "effective_from": salary_dto.effective_from.isoformat(),
                    "effective_to": (
                        salary_dto.effective_to.isoformat() if salary_dto.effective_to else None
                    ),
                    "is_active": salary_dto.is_active,
                    "updated_at": salary_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)
