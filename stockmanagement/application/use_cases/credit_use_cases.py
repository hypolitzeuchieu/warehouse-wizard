"""Credit use cases."""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone

from application.dto.credit_dto import (
    CreditCreateDTO,
    CreditPaymentCreateDTO,
    CreditPaymentResponseDTO,
    CreditResponseDTO,
)
from domain.credit.entities import Credit, CreditPayment, CreditStatus
from domain.credit.repositories import CreditPaymentRepository, CreditRepository
from domain.customer.repositories import CustomerRepository
from domain.notifications.services import NotificationDomainService
from shared.exceptions.base import BaseAPIException
from shared.exceptions.specific import (
    BadRequestError,
    NotFoundError,
)

logger = logging.getLogger(__name__)


def _credit_to_dto(credit: Credit) -> CreditResponseDTO:
    """Convert credit entity to DTO (shared utility function)."""
    return CreditResponseDTO(
        id=credit.id,
        business_id=credit.business_id,
        customer_id=credit.customer_id,
        invoice_id=credit.invoice_id,
        amount=credit.amount,
        paid_amount=credit.paid_amount,
        remaining_amount=credit.remaining_amount,
        due_date=credit.due_date,
        status=credit.status.value,
        notes=credit.notes,
        is_overdue=credit.is_overdue(),
        created_at=credit.created_at,
        updated_at=credit.updated_at,
    )


class CreateCreditUseCase:
    """Use case for creating a credit."""

    def __init__(
        self,
        credit_repository: CreditRepository,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.credit_repository = credit_repository
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: CreditCreateDTO) -> CreditResponseDTO:
        """Execute credit creation."""
        # Create credit entity
        credit = Credit(
            id=uuid4(),
            business_id=self.business_id,
            customer_id=dto.customer_id,
            invoice_id=dto.invoice_id,
            amount=dto.amount,
            paid_amount=Decimal("0.00"),
            remaining_amount=dto.amount,
            due_date=dto.due_date,
            status=CreditStatus.PENDING,
            notes=dto.notes,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            created_by=self.user_id,
        )

        credit.update_status()
        credit = self.credit_repository.create(credit)

        return self._to_dto(credit)

    def _to_dto(self, credit: Credit) -> CreditResponseDTO:
        """Convert credit entity to DTO."""
        return _credit_to_dto(credit)


class GetCreditUseCase:
    """Use case for getting a credit by ID."""

    def __init__(
        self,
        credit_repository: CreditRepository,
        credit_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.credit_repository = credit_repository
        self.credit_id = credit_id

    def execute(self) -> CreditResponseDTO:
        """Execute getting credit."""
        credit = self.credit_repository.get_by_id(self.credit_id)
        if not credit:
            raise NotFoundError(
                detail="Credit not found",
                code="CREDIT_NOT_FOUND",
            )

        return self._to_dto(credit)

    def _to_dto(self, credit: Credit) -> CreditResponseDTO:
        """Convert credit entity to DTO."""
        return _credit_to_dto(credit)


class ListCreditsUseCase:
    """Use case for listing credits."""

    def __init__(
        self,
        credit_repository: CreditRepository,
        business_id: UUID,
        customer_id: UUID | None = None,
        status: CreditStatus | None = None,
        overdue_only: bool = False,
    ) -> None:
        """Initialize use case."""
        self.credit_repository = credit_repository
        self.business_id = business_id
        self.customer_id = customer_id
        self.status = status
        self.overdue_only = overdue_only

    def execute(self) -> list[CreditResponseDTO]:
        """Execute listing credits."""
        if self.customer_id:
            credits = self.credit_repository.get_by_customer(
                customer_id=self.customer_id,
                business_id=self.business_id,
            )
        else:
            credits = self.credit_repository.get_by_business(
                business_id=self.business_id,
                status=self.status,
                overdue_only=self.overdue_only,
            )

        return [self._to_dto(credit) for credit in credits]

    def _to_dto(self, credit: Credit) -> CreditResponseDTO:
        """Convert credit entity to DTO."""
        return _credit_to_dto(credit)


class PayCreditUseCase:
    """Use case for paying a credit."""

    def __init__(
        self,
        credit_repository: CreditRepository,
        credit_payment_repository: CreditPaymentRepository,
        credit_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.credit_repository = credit_repository
        self.credit_payment_repository = credit_payment_repository
        self.credit_id = credit_id
        self.user_id = user_id

    @transaction.atomic
    def execute(
        self, dto: CreditPaymentCreateDTO
    ) -> tuple[CreditResponseDTO, CreditPaymentResponseDTO]:
        """Execute credit payment."""
        credit = self.credit_repository.get_by_id_for_update(self.credit_id)
        if not credit:
            raise NotFoundError(
                detail="Credit not found",
                code="CREDIT_NOT_FOUND",
            )

        if credit.status == CreditStatus.SETTLED:
            raise BadRequestError(
                detail="Credit is already fully paid",
                code="CREDIT_ALREADY_SETTLED",
            )

        if dto.amount > credit.remaining_amount:
            raise BaseAPIException(
                detail=f"Payment amount ({dto.amount}) exceeds remaining amount ({credit.remaining_amount})",
                code="PAYMENT_EXCEEDS_REMAINING",
                status_code=400,
            )

        payment_date = dto.payment_date or timezone.now()
        payment = CreditPayment(
            id=uuid4(),
            credit_id=self.credit_id,
            amount=dto.amount,
            payment_date=payment_date,
            payment_method=dto.payment_method,
            notes=dto.notes,
            created_at=timezone.now(),
            created_by=self.user_id,
        )

        payment = self.credit_payment_repository.create(payment)

        credit.paid_amount += dto.amount
        credit.remaining_amount -= dto.amount
        credit.updated_at = timezone.now()
        credit.update_status()
        credit = self.credit_repository.update(credit)

        return self._to_credit_dto(credit), self._to_payment_dto(payment)

    def _to_credit_dto(self, credit: Credit) -> CreditResponseDTO:
        """Convert credit entity to DTO."""
        return _credit_to_dto(credit)

    def _to_payment_dto(self, payment: CreditPayment) -> CreditPaymentResponseDTO:
        """Convert payment entity to DTO."""
        return CreditPaymentResponseDTO(
            id=payment.id,
            credit_id=payment.credit_id,
            amount=payment.amount,
            payment_date=payment.payment_date,
            payment_method=payment.payment_method,
            notes=payment.notes,
            created_at=payment.created_at,
        )


class GetCreditPaymentsUseCase:
    """Use case for getting credit payment history."""

    def __init__(
        self,
        credit_payment_repository: CreditPaymentRepository,
        credit_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.credit_payment_repository = credit_payment_repository
        self.credit_id = credit_id

    def execute(self) -> list[CreditPaymentResponseDTO]:
        """Execute getting credit payments."""
        payments = self.credit_payment_repository.get_by_credit(self.credit_id)
        return [self._to_dto(payment) for payment in payments]

    def _to_dto(self, payment: CreditPayment) -> CreditPaymentResponseDTO:
        """Convert payment entity to DTO."""
        return CreditPaymentResponseDTO(
            id=payment.id,
            credit_id=payment.credit_id,
            amount=payment.amount,
            payment_date=payment.payment_date,
            payment_method=payment.payment_method,
            notes=payment.notes,
            created_at=payment.created_at,
        )


class CheckOverdueCreditsUseCase:
    """Use case for checking and alerting on overdue credits."""

    def __init__(
        self,
        credit_repository: CreditRepository,
        customer_repository: CustomerRepository,
        notification_domain_service: NotificationDomainService,
        business_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.credit_repository = credit_repository
        self.customer_repository = customer_repository
        self.notification_domain_service = notification_domain_service
        self.business_id = business_id

    def execute(self) -> list[CreditResponseDTO]:
        """Execute checking overdue credits and create notifications."""
        overdue_credits = self.credit_repository.get_by_business(
            business_id=self.business_id,
            overdue_only=True,
        )

        # Update status for overdue credits
        for credit in overdue_credits:
            if credit.status != CreditStatus.OVERDUE:
                credit.update_status()
                if credit.status == CreditStatus.OVERDUE:
                    credit = self.credit_repository.update(credit)

        notifications_created = []
        for credit in overdue_credits:
            try:
                # Get customer
                customer = self.customer_repository.get_by_id(credit.customer_id)
                if not customer:
                    logger.warning(
                        f"Customer {credit.customer_id} not found for credit {credit.id}"
                    )
                    continue

                notifications = self.notification_domain_service.notify_payment_overdue(
                    credit_id=credit.id,
                    customer_name=customer.name,
                    remaining_amount=credit.remaining_amount,
                    due_date=credit.due_date,
                    business_id=self.business_id,
                )

                for notification in notifications:
                    notifications_created.append(
                        {
                            "credit_id": str(credit.id),
                            "customer_name": customer.name,
                            "notification_id": str(notification.id),
                        }
                    )

                if notifications:
                    logger.info(
                        f"Created {len(notifications)} overdue credit notifications for credit {credit.id}"
                    )

            except Exception as e:
                logger.error(
                    f"Error creating notification for overdue credit {credit.id}: {str(e)}",
                    exc_info=True,
                )

        return [self._to_dto(credit) for credit in overdue_credits]

    def _to_dto(self, credit: Credit) -> CreditResponseDTO:
        """Convert credit entity to DTO."""
        return _credit_to_dto(credit)
