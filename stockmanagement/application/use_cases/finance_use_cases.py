"""Finance use cases."""

from datetime import datetime
from uuid import UUID, uuid4

from django.utils import timezone

from application.dto.finance_dto import (
    ExpenseCreateDTO,
    ExpenseResponseDTO,
    ExpenseUpdateDTO,
)
from domain.business.services import BusinessDomainService
from domain.finance.entities import Expense, ExpenseType
from domain.finance.repositories import ExpenseRepository
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
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.expense_repository = expense_repository
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

        # Create expense entity
        expense = Expense(
            id=uuid4(),
            business_id=self.business_id,
            expense_type=expense_type,
            amount=dto.amount,
            reason=dto.reason,
            user_id=self.user_id,
            approved_by=None,
            is_approved=False,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        expense = self.expense_repository.create(expense)
        return self._to_dto(expense)

    def _to_dto(self, expense: Expense) -> ExpenseResponseDTO:
        """Convert expense entity to DTO."""
        return ExpenseResponseDTO(
            id=expense.id,
            business_id=expense.business_id,
            expense_type=expense.expense_type.value,
            amount=expense.amount,
            reason=expense.reason,
            user_id=expense.user_id,
            approved_by=expense.approved_by,
            is_approved=expense.is_approved,
            created_at=expense.created_at,
            updated_at=expense.updated_at,
        )


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
            user_id=expense.user_id,
            approved_by=expense.approved_by,
            is_approved=expense.is_approved,
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
            user_id=expense.user_id,
            approved_by=expense.approved_by,
            is_approved=expense.is_approved,
            created_at=expense.created_at,
            updated_at=expense.updated_at,
        )


class UpdateExpenseUseCase:
    """Use case for updating an expense."""

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
        return self._to_dto(expense)

    def _to_dto(self, expense: Expense) -> ExpenseResponseDTO:
        """Convert expense entity to DTO."""
        return ExpenseResponseDTO(
            id=expense.id,
            business_id=expense.business_id,
            expense_type=expense.expense_type.value,
            amount=expense.amount,
            reason=expense.reason,
            user_id=expense.user_id,
            approved_by=expense.approved_by,
            is_approved=expense.is_approved,
            created_at=expense.created_at,
            updated_at=expense.updated_at,
        )


class DeleteExpenseUseCase:
    """Use case for deleting an expense."""

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
