"""Salary use cases for managing employee salaries and promotions."""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID, uuid4

from django.utils import timezone

from application.dto.finance_dto import (
    SalaryCreateDTO,
    SalaryPromotionDTO,
    SalaryResponseDTO,
    SalaryUpdateDTO,
)
from domain.business.services import BusinessDomainService
from domain.finance.entities import Salary
from domain.finance.repositories import SalaryRepository
from shared.exceptions.base import BaseAPIException
from shared.exceptions.specific import (
    ForbiddenError,
    NotFoundError,
)
from shared.utils.validation import (
    validate_business_access,
    validate_entity_belongs_to_business,
)

logger = logging.getLogger(__name__)


class CreateSalaryUseCase:
    """Use case for creating a salary for an employee."""

    def __init__(
        self,
        salary_repository: SalaryRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,  # User creating the salary (owner/manager)
    ) -> None:
        """Initialize use case."""
        self.salary_repository = salary_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: SalaryCreateDTO) -> SalaryResponseDTO:
        """Execute salary creation."""
        # Check if user can manage members (owner/manager)
        if not self.business_domain_service.can_user_manage_members(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="Only owner or manager can create salaries",
                code="PERMISSION_DENIED",
            )

        # Check if user already has an active salary
        existing_salary = self.salary_repository.get_current_salary(
            business_id=self.business_id,
            user_id=dto.user_id,
        )

        if existing_salary and existing_salary.is_active():
            # End the existing salary
            existing_salary.effective_to = (dto.effective_from or timezone.now()) - timedelta(
                days=1
            )
            self.salary_repository.update(existing_salary)
            logger.info(
                f"Ended existing salary {existing_salary.id} for user {dto.user_id} "
                f"before creating new one"
            )

        # Create new salary
        effective_from = dto.effective_from or timezone.now()

        salary = Salary(
            id=uuid4(),
            business_id=self.business_id,
            user_id=dto.user_id,
            amount=dto.amount,
            currency=dto.currency,
            payment_frequency=dto.payment_frequency,
            deductions=dto.deductions,
            bonuses=dto.bonuses,
            effective_from=effective_from,
            effective_to=None,  # Active until explicitly ended
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        salary = self.salary_repository.create(salary)
        logger.info(
            f"Created salary {salary.id} for user {dto.user_id} in business {self.business_id}"
        )

        return self._to_dto(salary)

    def _to_dto(self, salary: Salary) -> SalaryResponseDTO:
        """Convert salary entity to DTO."""
        return SalaryResponseDTO(
            id=salary.id,
            business_id=salary.business_id,
            user_id=salary.user_id,
            amount=salary.amount,
            currency=salary.currency,
            payment_frequency=salary.payment_frequency,
            deductions=salary.deductions,
            bonuses=salary.bonuses,
            net_salary=salary.calculate_net_salary(),
            effective_from=salary.effective_from,
            effective_to=salary.effective_to,
            is_active=salary.is_active(),
            created_at=salary.created_at,
            updated_at=salary.updated_at,
        )


class PromoteEmployeeUseCase:
    """Use case for promoting an employee (creating new salary with higher amount)."""

    def __init__(
        self,
        salary_repository: SalaryRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        employee_id: UUID,
        user_id: UUID,  # User promoting (owner/manager)
    ) -> None:
        """Initialize use case."""
        self.salary_repository = salary_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.employee_id = employee_id
        self.user_id = user_id

    def execute(self, dto: SalaryPromotionDTO) -> SalaryResponseDTO:
        """Execute employee promotion."""
        # Check if user can manage members
        if not self.business_domain_service.can_user_manage_members(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="Only owner or manager can promote employees",
                code="PERMISSION_DENIED",
            )

        # Get current salary
        current_salary = self.salary_repository.get_current_salary(
            business_id=self.business_id,
            user_id=self.employee_id,
        )

        if not current_salary:
            raise NotFoundError(
                detail="Employee does not have an active salary",
                code="NO_ACTIVE_SALARY",
            )

        # Validate promotion (new amount should be higher)
        if dto.new_amount <= current_salary.amount:
            raise BaseAPIException(
                detail=f"Promotion amount ({dto.new_amount}) must be higher than current salary ({current_salary.amount})",
                code="INVALID_PROMOTION_AMOUNT",
                status_code=400,
            )

        # End current salary
        effective_from = dto.effective_from or timezone.now()
        current_salary.effective_to = effective_from - timedelta(days=1)
        self.salary_repository.update(current_salary)

        # Create new salary with promotion
        new_salary = Salary(
            id=uuid4(),
            business_id=self.business_id,
            user_id=self.employee_id,
            amount=dto.new_amount,
            currency=dto.currency or current_salary.currency,
            payment_frequency=dto.payment_frequency or current_salary.payment_frequency,
            deductions=dto.deductions,
            bonuses=dto.bonuses,
            effective_from=effective_from,
            effective_to=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        new_salary = self.salary_repository.create(new_salary)
        logger.info(
            f"Promoted employee {self.employee_id} from {current_salary.amount} "
            f"to {dto.new_amount} in business {self.business_id}"
        )

        return self._to_dto(new_salary)

    def _to_dto(self, salary: Salary) -> SalaryResponseDTO:
        """Convert salary entity to DTO."""
        return SalaryResponseDTO(
            id=salary.id,
            business_id=salary.business_id,
            user_id=salary.user_id,
            amount=salary.amount,
            currency=salary.currency,
            payment_frequency=salary.payment_frequency,
            deductions=salary.deductions,
            bonuses=salary.bonuses,
            net_salary=salary.calculate_net_salary(),
            effective_from=salary.effective_from,
            effective_to=salary.effective_to,
            is_active=salary.is_active(),
            created_at=salary.created_at,
            updated_at=salary.updated_at,
        )


class GetSalaryUseCase:
    """Use case for getting a salary by ID."""

    def __init__(
        self,
        salary_repository: SalaryRepository,
        business_domain_service: BusinessDomainService,
        salary_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.salary_repository = salary_repository
        self.business_domain_service = business_domain_service
        self.salary_id = salary_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self) -> SalaryResponseDTO:
        """Execute getting salary."""
        # Check if user has access to business
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        salary = self.salary_repository.get_by_id(self.salary_id)
        validate_entity_belongs_to_business(
            entity=salary,
            business_id=self.business_id,
            entity_name="Salary",
        )

        return self._to_dto(salary)

    def _to_dto(self, salary: Salary) -> SalaryResponseDTO:
        """Convert salary entity to DTO."""
        return SalaryResponseDTO(
            id=salary.id,
            business_id=salary.business_id,
            user_id=salary.user_id,
            amount=salary.amount,
            currency=salary.currency,
            payment_frequency=salary.payment_frequency,
            deductions=salary.deductions,
            bonuses=salary.bonuses,
            net_salary=salary.calculate_net_salary(),
            effective_from=salary.effective_from,
            effective_to=salary.effective_to,
            is_active=salary.is_active(),
            created_at=salary.created_at,
            updated_at=salary.updated_at,
        )


class GetSalaryHistoryUseCase:
    """Use case for getting salary history for a user."""

    def __init__(
        self,
        salary_repository: SalaryRepository,
        business_domain_service: BusinessDomainService,
        user_id: UUID,
        business_id: UUID,
        requester_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.salary_repository = salary_repository
        self.business_domain_service = business_domain_service
        self.user_id = user_id
        self.business_id = business_id
        self.requester_id = requester_id

    def execute(self) -> list[SalaryResponseDTO]:
        """Execute getting salary history."""
        # Check if user has access to business
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.requester_id,
        )

        # Users can only see their own salary history unless they're owner/manager
        if self.user_id != self.requester_id:
            if not self.business_domain_service.can_user_manage_members(
                self.business_id, self.requester_id
            ):
                raise ForbiddenError(
                    detail="You can only view your own salary history",
                    code="PERMISSION_DENIED",
                )

        salaries = self.salary_repository.get_by_user(self.user_id)
        # Filter by business
        business_salaries = [s for s in salaries if s.business_id == self.business_id]

        return [self._to_dto(salary) for salary in business_salaries]

    def _to_dto(self, salary: Salary) -> SalaryResponseDTO:
        """Convert salary entity to DTO."""
        return SalaryResponseDTO(
            id=salary.id,
            business_id=salary.business_id,
            user_id=salary.user_id,
            amount=salary.amount,
            currency=salary.currency,
            payment_frequency=salary.payment_frequency,
            deductions=salary.deductions,
            bonuses=salary.bonuses,
            net_salary=salary.calculate_net_salary(),
            effective_from=salary.effective_from,
            effective_to=salary.effective_to,
            is_active=salary.is_active(),
            created_at=salary.created_at,
            updated_at=salary.updated_at,
        )


class UpdateSalaryUseCase:
    """Use case for updating a salary."""

    def __init__(
        self,
        salary_repository: SalaryRepository,
        business_domain_service: BusinessDomainService,
        salary_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.salary_repository = salary_repository
        self.business_domain_service = business_domain_service
        self.salary_id = salary_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: SalaryUpdateDTO) -> SalaryResponseDTO:
        """Execute salary update."""
        # Check if user can manage members
        if not self.business_domain_service.can_user_manage_members(self.business_id, self.user_id):
            raise ForbiddenError(
                detail="Only owner or manager can update salaries",
                code="PERMISSION_DENIED",
            )

        salary = self.salary_repository.get_by_id(self.salary_id)
        validate_entity_belongs_to_business(
            entity=salary,
            business_id=self.business_id,
            entity_name="Salary",
        )

        # Update fields
        if dto.amount is not None:
            salary.amount = dto.amount
        if dto.currency is not None:
            salary.currency = dto.currency
        if dto.payment_frequency is not None:
            salary.payment_frequency = dto.payment_frequency
        if dto.deductions is not None:
            salary.deductions = dto.deductions
        if dto.bonuses is not None:
            salary.bonuses = dto.bonuses
        if dto.effective_from is not None:
            salary.effective_from = dto.effective_from
        if dto.effective_to is not None:
            salary.effective_to = dto.effective_to

        salary.updated_at = timezone.now()
        salary = self.salary_repository.update(salary)

        return self._to_dto(salary)

    def _to_dto(self, salary: Salary) -> SalaryResponseDTO:
        """Convert salary entity to DTO."""
        return SalaryResponseDTO(
            id=salary.id,
            business_id=salary.business_id,
            user_id=salary.user_id,
            amount=salary.amount,
            currency=salary.currency,
            payment_frequency=salary.payment_frequency,
            deductions=salary.deductions,
            bonuses=salary.bonuses,
            net_salary=salary.calculate_net_salary(),
            effective_from=salary.effective_from,
            effective_to=salary.effective_to,
            is_active=salary.is_active(),
            created_at=salary.created_at,
            updated_at=salary.updated_at,
        )
