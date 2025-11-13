"""Customer domain repositories (interfaces)."""

from abc import ABC, abstractmethod
from uuid import UUID

from domain.customer.entities import Customer, CustomerPurchaseHistory


class CustomerRepository(ABC):
    """Customer repository interface."""

    @abstractmethod
    def get_by_id(self, customer_id: UUID) -> Customer | None:
        """Get customer by ID."""
        pass

    @abstractmethod
    def get_by_email(self, email: str, business_id: UUID | None = None) -> Customer | None:
        """Get customer by email."""
        pass

    @abstractmethod
    def get_by_phone(self, phone_number: str, business_id: UUID | None = None) -> Customer | None:
        """Get customer by phone number."""
        pass

    @abstractmethod
    def get_by_business(self, business_id: UUID, limit: int = 100) -> list[Customer]:
        """Get customers for a business."""
        pass

    @abstractmethod
    def create(self, customer: Customer) -> Customer:
        """Create a new customer."""
        pass

    @abstractmethod
    def update(self, customer: Customer) -> Customer:
        """Update an existing customer."""
        pass

    @abstractmethod
    def delete(self, customer_id: UUID) -> None:
        """Delete a customer."""
        pass


class CustomerPurchaseHistoryRepository(ABC):
    """Customer purchase history repository interface."""

    @abstractmethod
    def get_by_customer(self, customer_id: UUID, limit: int = 100) -> list[CustomerPurchaseHistory]:
        """Get purchase history for a customer."""
        pass

    @abstractmethod
    def create(self, history: CustomerPurchaseHistory) -> CustomerPurchaseHistory:
        """Create a new purchase history record."""
        pass
