"""Credit domain repositories (interfaces)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from uuid import UUID

from domain.credit.entities import Credit, CreditPayment, CreditStatus


class CreditRepository(ABC):
    """Credit repository interface."""

    @abstractmethod
    def get_by_id(self, credit_id: UUID) -> Credit | None:
        """Get credit by ID."""
        pass

    @abstractmethod
    def get_by_id_for_update(self, credit_id: UUID) -> Credit | None:
        """Get credit by ID with row lock for update (prevents race conditions)."""
        pass

    @abstractmethod
    def get_by_customer(
        self, customer_id: UUID, business_id: UUID, limit: int = 100
    ) -> list[Credit]:
        """Get all credits for a customer."""
        pass

    @abstractmethod
    def get_by_business(
        self,
        business_id: UUID,
        status: CreditStatus | None = None,
        overdue_only: bool = False,
        limit: int = 100,
    ) -> list[Credit]:
        """Get all credits for a business with optional filters."""
        pass

    @abstractmethod
    def get_by_invoice(self, invoice_id: UUID) -> Credit | None:
        """Get credit by invoice ID."""
        pass

    @abstractmethod
    def get_by_invoice_for_update(self, invoice_id: UUID) -> Credit | None:
        """Get credit by invoice ID with row lock for update (prevents race conditions)."""
        pass

    @abstractmethod
    def create(self, credit: Credit) -> Credit:
        """Create a new credit."""
        pass

    @abstractmethod
    def update(self, credit: Credit) -> Credit:
        """Update an existing credit."""
        pass

    @abstractmethod
    def delete(self, credit_id: UUID) -> None:
        """Delete a credit."""
        pass


class CreditPaymentRepository(ABC):
    """Credit payment repository interface."""

    @abstractmethod
    def get_by_id(self, payment_id: UUID) -> CreditPayment | None:
        """Get payment by ID."""
        pass

    @abstractmethod
    def get_by_credit(self, credit_id: UUID, limit: int = 100) -> list[CreditPayment]:
        """Get all payments for a credit."""
        pass

    @abstractmethod
    def create(self, payment: CreditPayment) -> CreditPayment:
        """Create a new payment."""
        pass

    @abstractmethod
    def get_total_paid(self, credit_id: UUID) -> Decimal:
        """Get total amount paid for a credit."""
        pass
