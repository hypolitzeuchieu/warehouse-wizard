"""Finance ViewSet for expenses and financial management."""

from __future__ import annotations

from uuid import UUID

from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from application.use_cases.finance_use_cases import (
    CreateExpenseUseCase,
    DeleteExpenseUseCase,
    GetExpenseUseCase,
    ListExpensesUseCase,
    UpdateExpenseUseCase,
)
from domain.business.services import BusinessDomainService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    ExpenseRepositoryImpl,
    SalaryRepositoryImpl,
)
from presentation.serializers.finance_serializers import (
    ExpenseCreateSerializer,
    ExpenseUpdateSerializer,
    SalaryCreateSerializer,
    SalaryPromotionSerializer,
    SalaryUpdateSerializer,
)
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

    @swagger_auto_schema(
        operation_summary="List expenses",
        operation_description="Get all expenses for a business with optional filters.",
        responses={200: "List of expenses", 403: "Permission denied"},
        tags=["Finance"],
    )
    @action(detail=False, methods=["get"], url_path="businesses/(?P<business_id>[^/.]+)/expenses")
    def list_expenses(self, request: Request, business_id: UUID) -> Response:
        """List all expenses for a business."""
        try:
            from application.dto.expense_list_filter_dto import ExpenseListFilterDTO
            from presentation.serializers.finance_serializers import ExpenseResponseSerializer
            from shared.security.query_params_validator import QueryParamsValidator

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
                },
            )
            filter_payload["filters"]["business_id"] = business_id
            filter_dto = ExpenseListFilterDTO.from_payload(filter_payload)

            use_case = ListExpensesUseCase(
                expense_repository=ExpenseRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
                expense_type=filter_dto.expense_type,
                start_date=filter_dto.start_date,
                end_date=filter_dto.end_date,
                limit=QueryParamsValidator.MAX_PAGE_SIZE,
            )
            expenses = use_case.execute()

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
        operation_description="Create a new expense for a business.",
        request_body=ExpenseCreateSerializer,
        responses={201: "Expense created", 400: "Validation error", 403: "Permission denied"},
        tags=["Finance"],
    )
    @action(detail=False, methods=["post"], url_path="businesses/(?P<business_id>[^/.]+)/expenses")
    def create_expense(self, request: Request, business_id: UUID) -> Response:
        """Create a new expense."""
        serializer = ExpenseCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = CreateExpenseUseCase(
                expense_repository=ExpenseRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                business_id=business_id,
                user_id=request.user.id,
            )
            expense_dto = use_case.execute(dto)

            return self.success(
                message="Expense created successfully",
                data={
                    "id": str(expense_dto.id),
                    "business_id": str(expense_dto.business_id),
                    "expense_type": expense_dto.expense_type,
                    "amount": str(expense_dto.amount),
                    "reason": expense_dto.reason,
                    "user_id": str(expense_dto.user_id),
                    "approved_by": (
                        str(expense_dto.approved_by) if expense_dto.approved_by else None
                    ),
                    "is_approved": expense_dto.is_approved,
                    "created_at": expense_dto.created_at.isoformat(),
                    "updated_at": expense_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Get expense",
        operation_description="Get expense details by ID.",
        responses={200: "Expense details", 403: "Permission denied", 404: "Expense not found"},
        tags=["Finance"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="businesses/(?P<business_id>[^/.]+)/expenses/(?P<expense_id>[^/.]+)",
    )
    def get_expense(self, request: Request, business_id: UUID, expense_id: UUID) -> Response:
        """Get expense by ID."""
        try:
            use_case = GetExpenseUseCase(
                expense_repository=ExpenseRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                expense_id=expense_id,
                business_id=business_id,
                user_id=request.user.id,
            )
            expense_dto = use_case.execute()

            return self.success(
                message="Expense retrieved successfully",
                data={
                    "id": str(expense_dto.id),
                    "business_id": str(expense_dto.business_id),
                    "expense_type": expense_dto.expense_type,
                    "amount": str(expense_dto.amount),
                    "reason": expense_dto.reason,
                    "user_id": str(expense_dto.user_id),
                    "approved_by": (
                        str(expense_dto.approved_by) if expense_dto.approved_by else None
                    ),
                    "is_approved": expense_dto.is_approved,
                    "created_at": expense_dto.created_at.isoformat(),
                    "updated_at": expense_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Update expense",
        operation_description="Update expense details. Only owner/manager can approve.",
        request_body=ExpenseUpdateSerializer,
        responses={200: "Expense updated", 403: "Permission denied", 404: "Expense not found"},
        tags=["Finance"],
        method="put",
    )
    @swagger_auto_schema(
        operation_summary="Update expense (partial)",
        operation_description="Partially update expense details. Only owner/manager can approve.",
        request_body=ExpenseUpdateSerializer,
        responses={200: "Expense updated", 403: "Permission denied", 404: "Expense not found"},
        tags=["Finance"],
        method="patch",
    )
    @action(
        detail=False,
        methods=["put", "patch"],
        url_path="businesses/(?P<business_id>[^/.]+)/expenses/(?P<expense_id>[^/.]+)",
    )
    def update_expense(self, request: Request, business_id: UUID, expense_id: UUID) -> Response:
        """Update expense."""
        serializer = ExpenseUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = UpdateExpenseUseCase(
                expense_repository=ExpenseRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                expense_id=expense_id,
                business_id=business_id,
                user_id=request.user.id,
            )
            expense_dto = use_case.execute(dto)

            return self.success(
                message="Expense updated successfully",
                data={
                    "id": str(expense_dto.id),
                    "expense_type": expense_dto.expense_type,
                    "amount": str(expense_dto.amount),
                    "reason": expense_dto.reason,
                    "approved_by": (
                        str(expense_dto.approved_by) if expense_dto.approved_by else None
                    ),
                    "is_approved": expense_dto.is_approved,
                    "updated_at": expense_dto.updated_at.isoformat(),
                },
                status_code=status.HTTP_200_OK,
            )
        except Exception as e:
            return self.handle_exception(e)

    @swagger_auto_schema(
        operation_summary="Delete expense",
        operation_description="Delete an expense.",
        responses={200: "Expense deleted", 403: "Permission denied", 404: "Expense not found"},
        tags=["Finance"],
    )
    @action(
        detail=False,
        methods=["delete"],
        url_path="businesses/(?P<business_id>[^/.]+)/expenses/(?P<expense_id>[^/.]+)",
    )
    def delete_expense(self, request: Request, business_id: UUID, expense_id: UUID) -> Response:
        """Delete expense."""
        try:
            use_case = DeleteExpenseUseCase(
                expense_repository=ExpenseRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                expense_id=expense_id,
                business_id=business_id,
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
        operation_description="Get all overdue credits for a business and create notifications.",
        responses={200: "List of overdue credits", 403: "Permission denied"},
        tags=["Finance"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="businesses/(?P<business_id>[^/.]+)/credits/overdue",
    )
    def get_overdue_credits(self, request: Request, business_id: UUID) -> Response:
        """Get overdue credits for a business."""
        try:
            from application.use_cases.credit_use_cases import CheckOverdueCreditsUseCase
            from infrastructure.persistence.repositories import CreditRepositoryImpl

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
        operation_description="Create a new salary for an employee.",
        request_body=SalaryCreateSerializer,
        responses={201: "Salary created", 400: "Validation error", 403: "Permission denied"},
        tags=["Finance"],
    )
    @action(detail=False, methods=["post"], url_path="businesses/(?P<business_id>[^/.]+)/salaries")
    def create_salary(self, request: Request, business_id: UUID) -> Response:
        """Create a new salary for an employee."""
        from application.use_cases.salary_use_cases import CreateSalaryUseCase

        serializer = SalaryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
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
        operation_description="Get salary details by ID.",
        responses={200: "Salary details", 403: "Permission denied", 404: "Salary not found"},
        tags=["Finance"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="businesses/(?P<business_id>[^/.]+)/salaries/(?P<salary_id>[^/.]+)",
    )
    def get_salary(self, request: Request, business_id: UUID, salary_id: UUID) -> Response:
        """Get salary by ID."""
        from application.use_cases.salary_use_cases import GetSalaryUseCase

        try:
            use_case = GetSalaryUseCase(
                salary_repository=SalaryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                salary_id=salary_id,
                business_id=business_id,
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
        operation_description="Get salary history for a user. Users can only see their own history unless they're owner/manager.",
        responses={200: "Salary history", 403: "Permission denied"},
        tags=["Finance"],
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="businesses/(?P<business_id>[^/.]+)/salaries/user/(?P<user_id>[^/.]+)/history",
    )
    def get_salary_history(self, request: Request, business_id: UUID, user_id: UUID) -> Response:
        """Get salary history for a user."""
        from application.use_cases.salary_use_cases import GetSalaryHistoryUseCase

        try:
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
        operation_description="Promote an employee by creating a new salary with higher amount.",
        request_body=SalaryPromotionSerializer,
        responses={201: "Employee promoted", 400: "Validation error", 403: "Permission denied"},
        tags=["Finance"],
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="businesses/(?P<business_id>[^/.]+)/salaries/employee/(?P<employee_id>[^/.]+)/promote",
    )
    def promote_employee(self, request: Request, business_id: UUID, employee_id: UUID) -> Response:
        """Promote an employee (create new salary with higher amount)."""
        from application.use_cases.salary_use_cases import PromoteEmployeeUseCase

        serializer = SalaryPromotionSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
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
        operation_description="Update salary details. Only owner/manager can update.",
        request_body=SalaryUpdateSerializer,
        responses={200: "Salary updated", 403: "Permission denied", 404: "Salary not found"},
        tags=["Finance"],
        method="put",
    )
    @swagger_auto_schema(
        operation_summary="Update salary (partial)",
        operation_description="Partially update salary details. Only owner/manager can update.",
        request_body=SalaryUpdateSerializer,
        responses={200: "Salary updated", 403: "Permission denied", 404: "Salary not found"},
        tags=["Finance"],
        method="patch",
    )
    @action(
        detail=False,
        methods=["put", "patch"],
        url_path="businesses/(?P<business_id>[^/.]+)/salaries/(?P<salary_id>[^/.]+)",
    )
    def update_salary(self, request: Request, business_id: UUID, salary_id: UUID) -> Response:
        """Update salary."""
        from application.use_cases.salary_use_cases import UpdateSalaryUseCase

        serializer = SalaryUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.handle_validation_error(serializer)

        try:
            dto = serializer.to_dto()
            use_case = UpdateSalaryUseCase(
                salary_repository=SalaryRepositoryImpl(),
                business_domain_service=self._get_business_domain_service(),
                salary_id=salary_id,
                business_id=business_id,
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
