"""Credit use cases."""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID, uuid4

from django.utils import timezone

from application.dto.credit_dto import (
    CreditCreateDTO,
    CreditPaymentCreateDTO,
    CreditPaymentResponseDTO,
    CreditResponseDTO,
)
from domain.credit.entities import Credit, CreditPayment, CreditStatus
from domain.credit.repositories import CreditPaymentRepository, CreditRepository
from shared.exceptions.base import BaseAPIException
from shared.exceptions.specific import (
    BadRequestError,
    NotFoundError,
)

logger = logging.getLogger(__name__)


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

    def execute(
        self, dto: CreditPaymentCreateDTO
    ) -> tuple[CreditResponseDTO, CreditPaymentResponseDTO]:
        """Execute credit payment."""
        # Get credit
        credit = self.credit_repository.get_by_id(self.credit_id)
        if not credit:
            raise NotFoundError(
                detail="Credit not found",
                code="CREDIT_NOT_FOUND",
            )

        # Check if credit is already settled
        if credit.status == CreditStatus.SETTLED:
            raise BadRequestError(
                detail="Credit is already fully paid",
                code="CREDIT_ALREADY_SETTLED",
            )

        # Validate payment amount
        if dto.amount > credit.remaining_amount:
            raise BaseAPIException(
                detail=f"Payment amount ({dto.amount}) exceeds remaining amount ({credit.remaining_amount})",
                code="PAYMENT_EXCEEDS_REMAINING",
                status_code=400,
            )

        # Create payment
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

        # Update credit
        credit.paid_amount += dto.amount
        credit.remaining_amount -= dto.amount
        credit.updated_at = timezone.now()
        credit.update_status()
        credit = self.credit_repository.update(credit)

        return self._to_credit_dto(credit), self._to_payment_dto(payment)

    def _to_credit_dto(self, credit: Credit) -> CreditResponseDTO:
        """Convert credit entity to DTO."""
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
        business_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.credit_repository = credit_repository
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

        # Create notifications for overdue credits
        from infrastructure.persistence.models.business_models import Business as BusinessModel
        from infrastructure.persistence.models.business_models import (
            BusinessMember as BusinessMemberModel,
        )
        from infrastructure.persistence.models.customer_models import Customer as CustomerModel
        from infrastructure.persistence.models.notification_models import Notification

        notifications_created = []
        for credit in overdue_credits:
            try:
                # Get customer
                customer = CustomerModel.objects.get(id=credit.customer_id)
                business = BusinessModel.objects.get(id=self.business_id)

                # Check if notification already exists (within last 24 hours)
                from datetime import timedelta

                recent_notification = (
                    Notification.objects.filter(
                        notification_type="PAYMENT_OVERDUE",
                        created_at__gte=timezone.now() - timedelta(hours=24),
                    )
                    .filter(message__icontains=str(credit.id))
                    .first()
                )

                if not recent_notification:
                    # Notify owner
                    owner = business.owner
                    if owner:
                        notification = Notification.objects.create(
                            product=None,  # No product for credit notifications
                            user=owner,
                            notification_type="PAYMENT_OVERDUE",
                            message=f"Credit for customer '{customer.name}' is overdue. Amount: {credit.remaining_amount}, Due date: {credit.due_date.strftime('%Y-%m-%d')}.",
                            status="UNREAD",
                        )
                        notifications_created.append(
                            {
                                "credit_id": str(credit.id),
                                "customer_name": customer.name,
                                "notification_id": str(notification.id),
                            }
                        )

                    # Notify managers
                    managers = BusinessMemberModel.objects.filter(
                        business_id=self.business_id,
                        role="manager",
                        is_active=True,
                    ).select_related("user")

                    for manager_member in managers:
                        notification = Notification.objects.create(
                            product=None,
                            user=manager_member.user,
                            notification_type="PAYMENT_OVERDUE",
                            message=f"Credit for customer '{customer.name}' is overdue. Amount: {credit.remaining_amount}, Due date: {credit.due_date.strftime('%Y-%m-%d')}.",
                            status="UNREAD",
                        )
                        notifications_created.append(
                            {
                                "credit_id": str(credit.id),
                                "customer_name": customer.name,
                                "notification_id": str(notification.id),
                                "user_id": str(manager_member.user.id),
                            }
                        )

                    logger.info(f"Created overdue credit notification for credit {credit.id}")

            except Exception as e:
                logger.error(
                    f"Error creating notification for overdue credit {credit.id}: {str(e)}"
                )

        return [self._to_dto(credit) for credit in overdue_credits]

    def _to_dto(self, credit: Credit) -> CreditResponseDTO:
        """Convert credit entity to DTO."""
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
