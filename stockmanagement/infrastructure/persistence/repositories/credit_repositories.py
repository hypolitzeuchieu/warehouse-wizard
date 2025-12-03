"""Credit repository implementations."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db.models import Q, Sum
from django.utils import timezone

from domain.credit.entities import Credit, CreditPayment, CreditStatus
from domain.credit.repositories import CreditPaymentRepository, CreditRepository
from infrastructure.persistence.models.credit_models import (
    Credit as CreditModel,
)
from infrastructure.persistence.models.credit_models import (
    CreditPayment as CreditPaymentModel,
)


class CreditRepositoryImpl(CreditRepository):
    """Django implementation of CreditRepository."""

    def get_by_id(self, credit_id: UUID) -> Credit | None:
        """Get credit by ID."""
        try:
            credit_model = CreditModel.objects.select_related(
                "business", "customer", "invoice", "created_by"
            ).get(id=credit_id)
            return self._to_entity(credit_model)
        except CreditModel.DoesNotExist:
            return None

    def get_by_id_for_update(self, credit_id: UUID) -> Credit | None:
        """Get credit by ID with row lock for update (prevents race conditions)."""
        try:
            credit_model = (
                CreditModel.objects.select_related("business", "customer", "invoice", "created_by")
                .select_for_update()
                .get(id=credit_id)
            )
            return self._to_entity(credit_model)
        except CreditModel.DoesNotExist:
            return None

    def get_by_customer(
        self, customer_id: UUID, business_id: UUID, limit: int = 100
    ) -> list[Credit]:
        """Get all credits for a customer."""
        credits = (
            CreditModel.objects.filter(customer_id=customer_id, business_id=business_id)
            .select_related("business", "customer", "invoice")
            .order_by("-created_at")[:limit]
        )
        return [self._to_entity(credit) for credit in credits]

    def get_by_business(
        self,
        business_id: UUID,
        status: CreditStatus | None = None,
        overdue_only: bool = False,
        limit: int = 100,
    ) -> list[Credit]:
        """Get all credits for a business with optional filters."""
        query = CreditModel.objects.filter(business_id=business_id).select_related(
            "customer", "invoice"
        )

        if status:
            query = query.filter(status=status.value)

        if overdue_only:
            query = query.filter(
                Q(status__in=["PENDING", "PARTIALLY_PAID"]) & Q(due_date__lt=timezone.now())
            )

        credits = query.order_by("-created_at")[:limit]
        return [self._to_entity(credit) for credit in credits]

    def get_by_invoice(self, invoice_id: UUID) -> Credit | None:
        """Get credit by invoice ID."""
        try:
            credit_model = CreditModel.objects.select_related(
                "business", "customer", "invoice"
            ).get(invoice_id=invoice_id)
            return self._to_entity(credit_model)
        except CreditModel.DoesNotExist:
            return None

    def create(self, credit: Credit) -> Credit:
        """Create a new credit."""
        credit_model = CreditModel(
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
            created_by_id=credit.created_by,
        )
        credit_model.save()
        return self._to_entity(credit_model)

    def update(self, credit: Credit) -> Credit:
        """Update an existing credit."""
        credit_model = CreditModel.objects.get(id=credit.id)
        credit_model.amount = credit.amount
        credit_model.paid_amount = credit.paid_amount
        credit_model.remaining_amount = credit.remaining_amount
        credit_model.due_date = credit.due_date
        credit_model.status = credit.status.value
        credit_model.notes = credit.notes
        credit_model.save()
        return self._to_entity(credit_model)

    def delete(self, credit_id: UUID) -> None:
        """Delete a credit."""
        CreditModel.objects.filter(id=credit_id).delete()

    def _to_entity(self, credit_model: CreditModel) -> Credit:
        """Convert Django model to domain entity."""
        return Credit(
            id=credit_model.id,
            business_id=credit_model.business_id,
            customer_id=credit_model.customer_id,
            invoice_id=credit_model.invoice_id,
            amount=credit_model.amount,
            paid_amount=credit_model.paid_amount,
            remaining_amount=credit_model.remaining_amount,
            due_date=credit_model.due_date,
            status=CreditStatus(credit_model.status),
            notes=credit_model.notes,
            created_at=credit_model.created_at,
            updated_at=credit_model.updated_at,
            created_by=credit_model.created_by_id,
        )


class CreditPaymentRepositoryImpl(CreditPaymentRepository):
    """Django implementation of CreditPaymentRepository."""

    def get_by_id(self, payment_id: UUID) -> CreditPayment | None:
        """Get payment by ID."""
        try:
            payment_model = CreditPaymentModel.objects.select_related("credit", "created_by").get(
                id=payment_id
            )
            return self._to_entity(payment_model)
        except CreditPaymentModel.DoesNotExist:
            return None

    def get_by_credit(self, credit_id: UUID, limit: int = 100) -> list[CreditPayment]:
        """Get all payments for a credit."""
        payments = (
            CreditPaymentModel.objects.filter(credit_id=credit_id)
            .select_related("credit", "created_by")
            .order_by("-payment_date")[:limit]
        )
        return [self._to_entity(payment) for payment in payments]

    def create(self, payment: CreditPayment) -> CreditPayment:
        """Create a new payment."""
        payment_model = CreditPaymentModel(
            id=payment.id,
            credit_id=payment.credit_id,
            amount=payment.amount,
            payment_date=payment.payment_date,
            payment_method=payment.payment_method,
            notes=payment.notes,
            created_by_id=payment.created_by,
        )
        payment_model.save()
        return self._to_entity(payment_model)

    def get_total_paid(self, credit_id: UUID) -> Decimal:
        """Get total amount paid for a credit."""
        total = CreditPaymentModel.objects.filter(credit_id=credit_id).aggregate(
            total=Sum("amount")
        )["total"]
        return Decimal(total) if total else Decimal("0.00")

    def _to_entity(self, payment_model: CreditPaymentModel) -> CreditPayment:
        """Convert Django model to domain entity."""
        return CreditPayment(
            id=payment_model.id,
            credit_id=payment_model.credit_id,
            amount=payment_model.amount,
            payment_date=payment_model.payment_date,
            payment_method=payment_model.payment_method,
            notes=payment_model.notes,
            created_at=payment_model.created_at,
            created_by=payment_model.created_by_id,
        )
