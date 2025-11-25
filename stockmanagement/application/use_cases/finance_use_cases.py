"""Finance use cases."""

from copy import deepcopy
from datetime import datetime
from uuid import UUID, uuid4

from django.utils import timezone

from application.dto.finance_dto import (
    ExpenseAuditLogDTO,
    ExpenseCategoryStatsDTO,
    ExpenseCreateDTO,
    ExpenseResponseDTO,
    ExpenseSummaryDTO,
    ExpenseUpdateDTO,
    MonthlyExpenseStatDTO,
)
from domain.business.services import BusinessDomainService
from domain.finance.entities import (
    Expense,
    ExpenseAuditLog,
    ExpensePayeeType,
    ExpensePaymentMethod,
    ExpenseType,
)
from domain.finance.repositories import ExpenseAuditLogRepository, ExpenseRepository
from shared.exceptions.specific import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)


class CreateExpenseUseCase:
    """Use case for creating an expense."""

    def __init__(
        self,
        expense_repository: ExpenseRepository,
        audit_log_repository: ExpenseAuditLogRepository | None,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.expense_repository = expense_repository
        self.audit_log_repository = audit_log_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: ExpenseCreateDTO) -> ExpenseResponseDTO:
        """Execute expense creation."""
        # Check if user has access to business
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        # Validate expense type
        try:
            expense_type = ExpenseType(dto.expense_type)
        except ValueError as err:
            raise BadRequestError(
                detail="Invalid expense type",
                code="INVALID_EXPENSE_TYPE",
            ) from err

        # Validate payment metadata
        try:
            payment_method = ExpensePaymentMethod(dto.payment_method)
        except ValueError as err:
            raise BadRequestError(
                detail="Invalid payment method",
                code="INVALID_PAYMENT_METHOD",
            ) from err

        try:
            payee_type = ExpensePayeeType(dto.payee_type)
        except ValueError as err:
            raise BadRequestError(
                detail="Invalid payee type",
                code="INVALID_PAYEE_TYPE",
            ) from err

        # Create expense entity
        expense = Expense(
            id=uuid4(),
            business_id=self.business_id,
            expense_type=expense_type,
            amount=dto.amount,
            reason=dto.reason,
            reason_details=dto.reason_details,
            user_id=self.user_id,
            approved_by=None,
            is_approved=False,
            payment_method=payment_method,
            payment_reference=dto.payment_reference,
            payee_type=payee_type,
            payee_name=dto.payee_name,
            justification_metadata=dto.justification_metadata or {},
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        expense = self.expense_repository.create(expense)
        self._record_audit(expense=expense, action="CREATED", before_state=None)
        return self._to_dto(expense)

    def _to_dto(self, expense: Expense) -> ExpenseResponseDTO:
        """Convert expense entity to DTO."""
        return ExpenseResponseDTO(
            id=expense.id,
            business_id=expense.business_id,
            expense_type=expense.expense_type.value,
            amount=expense.amount,
            reason=expense.reason,
            reason_details=expense.reason_details,
            user_id=expense.user_id,
            approved_by=expense.approved_by,
            is_approved=expense.is_approved,
            payment_method=expense.payment_method.value,
            payment_reference=expense.payment_reference,
            payee_type=expense.payee_type.value,
            payee_name=expense.payee_name,
            justification_metadata=expense.justification_metadata,
            created_at=expense.created_at,
            updated_at=expense.updated_at,
        )

    def _record_audit(
        self,
        expense: Expense,
        action: str,
        before_state: Expense | None,
    ) -> None:
        """Persist audit log entry if repository is configured."""
        if not self.audit_log_repository:
            return

        log = ExpenseAuditLog(
            id=uuid4(),
            expense_id=expense.id,
            action=action,
            performed_by=self.user_id,
            amount_before=before_state.amount if before_state else None,
            amount_after=expense.amount,
            reason_before=before_state.reason if before_state else None,
            reason_after=expense.reason,
            reason_details_before=before_state.reason_details if before_state else None,
            reason_details_after=expense.reason_details,
            payment_method_before=(before_state.payment_method if before_state else None),
            payment_method_after=expense.payment_method,
            payee_type_before=before_state.payee_type if before_state else None,
            payee_type_after=expense.payee_type,
            payee_name_before=before_state.payee_name if before_state else None,
            payee_name_after=expense.payee_name,
            justification_snapshot=expense.justification_metadata.copy(),
            created_at=timezone.now(),
        )
        self.audit_log_repository.create(log)


class GetExpenseUseCase:
    """Use case for getting an expense by ID."""

    def __init__(
        self,
        expense_repository: ExpenseRepository,
        business_domain_service: BusinessDomainService,
        expense_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.expense_repository = expense_repository
        self.business_domain_service = business_domain_service
        self.expense_id = expense_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self) -> ExpenseResponseDTO:
        """Execute getting expense."""
        # Check if user has access to business
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        expense = self.expense_repository.get_by_id(self.expense_id)
        if not expense or expense.business_id != self.business_id:
            raise NotFoundError(
                detail="Expense not found",
                code="EXPENSE_NOT_FOUND",
            )

        return self._to_dto(expense)

    def _to_dto(self, expense: Expense) -> ExpenseResponseDTO:
        """Convert expense entity to DTO."""
        return ExpenseResponseDTO(
            id=expense.id,
            business_id=expense.business_id,
            expense_type=expense.expense_type.value,
            amount=expense.amount,
            reason=expense.reason,
            reason_details=expense.reason_details,
            user_id=expense.user_id,
            approved_by=expense.approved_by,
            is_approved=expense.is_approved,
            payment_method=expense.payment_method.value,
            payment_reference=expense.payment_reference,
            payee_type=expense.payee_type.value,
            payee_name=expense.payee_name,
            justification_metadata=expense.justification_metadata,
            created_at=expense.created_at,
            updated_at=expense.updated_at,
        )


class ListExpensesUseCase:
    """Use case for listing expenses for a business."""

    def __init__(
        self,
        expense_repository: ExpenseRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        expense_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        payment_method: str | None = None,
        payee_type: str | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        is_approved: bool | None = None,
        limit: int = 100,
    ) -> None:
        """Initialize use case."""
        self.expense_repository = expense_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.expense_type = ExpenseType(expense_type) if expense_type else None
        self.start_date = start_date
        self.end_date = end_date
        self.payment_method = ExpensePaymentMethod(payment_method) if payment_method else None
        self.payee_type = ExpensePayeeType(payee_type) if payee_type else None
        self.min_amount = min_amount
        self.max_amount = max_amount
        self.is_approved = is_approved
        self.limit = limit

    def execute(self) -> list[ExpenseResponseDTO]:
        """Execute listing expenses."""
        # Check if user has access to business
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        expenses = self.expense_repository.get_by_business(
            business_id=self.business_id,
            expense_type=self.expense_type,
            start_date=self.start_date,
            end_date=self.end_date,
            payment_method=self.payment_method.value if self.payment_method else None,
            payee_type=self.payee_type.value if self.payee_type else None,
            min_amount=self.min_amount,
            max_amount=self.max_amount,
            is_approved=self.is_approved,
            limit=self.limit,
        )

        return [self._to_dto(expense) for expense in expenses]

    def _to_dto(self, expense: Expense) -> ExpenseResponseDTO:
        """Convert expense entity to DTO."""
        return ExpenseResponseDTO(
            id=expense.id,
            business_id=expense.business_id,
            expense_type=expense.expense_type.value,
            amount=expense.amount,
            reason=expense.reason,
            reason_details=expense.reason_details,
            user_id=expense.user_id,
            approved_by=expense.approved_by,
            is_approved=expense.is_approved,
            payment_method=expense.payment_method.value,
            payment_reference=expense.payment_reference,
            payee_type=expense.payee_type.value,
            payee_name=expense.payee_name,
            justification_metadata=expense.justification_metadata,
            created_at=expense.created_at,
            updated_at=expense.updated_at,
        )


class UpdateExpenseUseCase:
    """Use case for updating an expense."""

    def __init__(
        self,
        expense_repository: ExpenseRepository,
        audit_log_repository: ExpenseAuditLogRepository | None,
        business_domain_service: BusinessDomainService,
        expense_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.expense_repository = expense_repository
        self.audit_log_repository = audit_log_repository
        self.business_domain_service = business_domain_service
        self.expense_id = expense_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: ExpenseUpdateDTO) -> ExpenseResponseDTO:
        """Execute expense update."""
        # Check if user has access to business
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        expense = self.expense_repository.get_by_id(self.expense_id)
        if not expense or expense.business_id != self.business_id:
            raise NotFoundError(
                detail="Expense not found",
                code="EXPENSE_NOT_FOUND",
            )

        before_state = deepcopy(expense)

        # Update fields
        if dto.expense_type is not None:
            try:
                expense.expense_type = ExpenseType(dto.expense_type)
            except ValueError as err:
                raise BadRequestError(
                    detail="Invalid expense type",
                    code="INVALID_EXPENSE_TYPE",
                ) from err
        if dto.amount is not None:
            expense.amount = dto.amount
        if dto.reason is not None:
            expense.reason = dto.reason
        if dto.reason_details is not None:
            expense.reason_details = dto.reason_details
        if dto.payment_method is not None:
            try:
                expense.payment_method = ExpensePaymentMethod(dto.payment_method)
            except ValueError as err:
                raise BadRequestError(
                    detail="Invalid payment method",
                    code="INVALID_PAYMENT_METHOD",
                ) from err
        if dto.payment_reference is not None:
            expense.payment_reference = dto.payment_reference
        if dto.payee_type is not None:
            try:
                expense.payee_type = ExpensePayeeType(dto.payee_type)
            except ValueError as err:
                raise BadRequestError(
                    detail="Invalid payee type",
                    code="INVALID_PAYEE_TYPE",
                ) from err
        if dto.payee_name is not None:
            expense.payee_name = dto.payee_name
        if dto.justification_metadata is not None:
            expense.justification_metadata = dto.justification_metadata
        if dto.is_approved is not None:
            # Only owner/manager can approve
            if dto.is_approved and not self.business_domain_service.can_user_manage_members(
                self.business_id, self.user_id
            ):
                raise ForbiddenError(
                    detail="Only owner or manager can approve expenses",
                    code="PERMISSION_DENIED",
                )
            expense.is_approved = dto.is_approved
            if dto.is_approved:
                expense.approved_by = self.user_id

        expense.updated_at = timezone.now()
        expense = self.expense_repository.update(expense)
        self._record_audit(
            before_state=before_state,
            after_state=expense,
            action=(
                "UPDATED"
                if dto.is_approved is None
                else "APPROVED" if dto.is_approved else "UPDATED"
            ),
        )
        return self._to_dto(expense)

    def _to_dto(self, expense: Expense) -> ExpenseResponseDTO:
        """Convert expense entity to DTO."""
        return ExpenseResponseDTO(
            id=expense.id,
            business_id=expense.business_id,
            expense_type=expense.expense_type.value,
            amount=expense.amount,
            reason=expense.reason,
            reason_details=expense.reason_details,
            user_id=expense.user_id,
            approved_by=expense.approved_by,
            is_approved=expense.is_approved,
            payment_method=expense.payment_method.value,
            payment_reference=expense.payment_reference,
            payee_type=expense.payee_type.value,
            payee_name=expense.payee_name,
            justification_metadata=expense.justification_metadata,
            created_at=expense.created_at,
            updated_at=expense.updated_at,
        )

    def _record_audit(
        self,
        before_state: Expense,
        after_state: Expense,
        action: str,
    ) -> None:
        if not self.audit_log_repository:
            return

        log = ExpenseAuditLog(
            id=uuid4(),
            expense_id=after_state.id,
            action=action,
            performed_by=self.user_id,
            amount_before=before_state.amount,
            amount_after=after_state.amount,
            reason_before=before_state.reason,
            reason_after=after_state.reason,
            reason_details_before=before_state.reason_details,
            reason_details_after=after_state.reason_details,
            payment_method_before=before_state.payment_method,
            payment_method_after=after_state.payment_method,
            payee_type_before=before_state.payee_type,
            payee_type_after=after_state.payee_type,
            payee_name_before=before_state.payee_name,
            payee_name_after=after_state.payee_name,
            justification_snapshot=after_state.justification_metadata.copy(),
            created_at=timezone.now(),
        )
        self.audit_log_repository.create(log)


class DeleteExpenseUseCase:
    """Use case for deleting an expense."""

    def __init__(
        self,
        expense_repository: ExpenseRepository,
        audit_log_repository: ExpenseAuditLogRepository | None,
        business_domain_service: BusinessDomainService,
        expense_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.expense_repository = expense_repository
        self.audit_log_repository = audit_log_repository
        self.business_domain_service = business_domain_service
        self.expense_id = expense_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self) -> None:
        """Execute expense deletion."""
        # Check if user has access to business
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        expense = self.expense_repository.get_by_id(self.expense_id)
        if not expense or expense.business_id != self.business_id:
            raise NotFoundError(
                detail="Expense not found",
                code="EXPENSE_NOT_FOUND",
            )

        self.expense_repository.delete(self.expense_id)
        if self.audit_log_repository:
            log = ExpenseAuditLog(
                id=uuid4(),
                expense_id=expense.id,
                action="DELETED",
                performed_by=self.user_id,
                amount_before=expense.amount,
                amount_after=None,
                reason_before=expense.reason,
                reason_after=None,
                reason_details_before=expense.reason_details,
                reason_details_after=None,
                payment_method_before=expense.payment_method,
                payment_method_after=None,
                payee_type_before=expense.payee_type,
                payee_type_after=None,
                payee_name_before=expense.payee_name,
                payee_name_after=None,
                justification_snapshot=expense.justification_metadata.copy(),
                created_at=timezone.now(),
            )
            self.audit_log_repository.create(log)


class GetExpenseHistoryUseCase:
    """Use case for returning audit history of an expense."""

    def __init__(
        self,
        audit_log_repository: ExpenseAuditLogRepository,
        business_domain_service: BusinessDomainService,
        expense_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        self.audit_log_repository = audit_log_repository
        self.business_domain_service = business_domain_service
        self.expense_id = expense_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self) -> list[ExpenseAuditLogDTO]:
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        logs = self.audit_log_repository.list_for_expense(self.expense_id)
        return [
            ExpenseAuditLogDTO(
                id=log.id,
                expense_id=log.expense_id,
                action=log.action,
                performed_by=log.performed_by,
                amount_before=log.amount_before,
                amount_after=log.amount_after,
                reason_before=log.reason_before,
                reason_after=log.reason_after,
                reason_details_before=log.reason_details_before,
                reason_details_after=log.reason_details_after,
                payment_method_before=(
                    log.payment_method_before.value if log.payment_method_before else None
                ),
                payment_method_after=(
                    log.payment_method_after.value if log.payment_method_after else None
                ),
                payee_type_before=log.payee_type_before.value if log.payee_type_before else None,
                payee_type_after=log.payee_type_after.value if log.payee_type_after else None,
                payee_name_before=log.payee_name_before,
                payee_name_after=log.payee_name_after,
                justification_snapshot=log.justification_snapshot,
                created_at=log.created_at,
            )
            for log in logs
        ]


class GetExpenseSummaryUseCase:
    """Use case returning aggregated expense analytics."""

    def __init__(
        self,
        expense_repository: ExpenseRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> None:
        self.expense_repository = expense_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.start_date = start_date
        self.end_date = end_date

    def execute(self) -> ExpenseSummaryDTO:
        if not self.business_domain_service.user_has_access(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="You don't have access to this business",
                code="PERMISSION_DENIED",
            )

        summary_data = self.expense_repository.get_summary(
            business_id=self.business_id,
            start_date=self.start_date,
            end_date=self.end_date,
        )

        by_type_stats = [
            ExpenseCategoryStatsDTO(
                expense_type=item["expense_type"],
                total_amount=item["total_amount"],
                count=item["count"],
                average_amount=item["average_amount"],
                percentage_of_total=item["percentage_of_total"],
            )
            for item in summary_data["by_type"]
        ]

        monthly_stats = [
            MonthlyExpenseStatDTO(
                month=item["month"],
                total_amount=item["total_amount"],
                count=item["count"],
            )
            for item in summary_data["monthly_stats"]
        ]

        return ExpenseSummaryDTO(
            business_id=self.business_id,
            total_amount=summary_data["total_amount"],
            total_count=summary_data["total_count"],
            by_type=by_type_stats,
            by_payment_method=summary_data["by_payment_method"],
            monthly_stats=monthly_stats,
        )
