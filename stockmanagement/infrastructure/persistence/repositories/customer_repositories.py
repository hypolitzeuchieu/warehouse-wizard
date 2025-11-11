"""Customer repository implementations."""

from typing import Optional
from uuid import UUID

from domain.customer.entities import Customer, CustomerPurchaseHistory
from domain.customer.repositories import (
    CustomerPurchaseHistoryRepository,
    CustomerRepository,
)
from infrastructure.persistence.models.customer_models import (
    Customer as CustomerModel,
    CustomerPurchaseHistory as CustomerPurchaseHistoryModel,
)


class CustomerRepositoryImpl(CustomerRepository):
    """Django implementation of CustomerRepository."""

    def get_by_id(self, customer_id: UUID) -> Optional[Customer]:
        """Get customer by ID."""
        try:
            customer_model = CustomerModel.objects.select_related(
                "business"
            ).get(id=customer_id)
            return self._to_entity(customer_model)
        except CustomerModel.DoesNotExist:
            return None

    def get_by_email(
        self, email: str, business_id: Optional[UUID] = None
    ) -> Optional[Customer]:
        """Get customer by email."""
        try:
            query = CustomerModel.objects.filter(email=email)
            if business_id:
                query = query.filter(business_id=business_id)
            customer_model = query.select_related("business").first()
            if customer_model:
                return self._to_entity(customer_model)
            return None
        except CustomerModel.DoesNotExist:
            return None

    def get_by_phone(
        self, phone_number: str, business_id: Optional[UUID] = None
    ) -> Optional[Customer]:
        """Get customer by phone number."""
        try:
            query = CustomerModel.objects.filter(phone_number=phone_number)
            if business_id:
                query = query.filter(business_id=business_id)
            customer_model = query.select_related("business").first()
            if customer_model:
                return self._to_entity(customer_model)
            return None
        except CustomerModel.DoesNotExist:
            return None

    def get_by_business(
        self, business_id: UUID, limit: int = 100
    ) -> list[Customer]:
        """Get customers for a business."""
        customers = CustomerModel.objects.filter(
            business_id=business_id
        ).select_related("business")[:limit]
        return [self._to_entity(customer) for customer in customers]

    def create(self, customer: Customer) -> Customer:
        """Create a new customer."""
        customer_model = CustomerModel(
            id=customer.id,
            business_id=customer.business_id,
            name=customer.name,
            email=customer.email,
            phone_number=customer.phone_number,
            address=customer.address,
            loyalty_points=customer.loyalty_points,
            total_purchases=customer.total_purchases,
        )
        customer_model.save()
        return self._to_entity(customer_model)

    def update(self, customer: Customer) -> Customer:
        """Update an existing customer."""
        customer_model = CustomerModel.objects.get(id=customer.id)
        customer_model.name = customer.name
        customer_model.email = customer.email
        customer_model.phone_number = customer.phone_number
        customer_model.address = customer.address
        customer_model.loyalty_points = customer.loyalty_points
        customer_model.total_purchases = customer.total_purchases
        customer_model.save()
        return self._to_entity(customer_model)

    def delete(self, customer_id: UUID) -> None:
        """Delete a customer."""
        CustomerModel.objects.filter(id=customer_id).delete()

    def _to_entity(self, customer_model: CustomerModel) -> Customer:
        """Convert Django model to domain entity."""
        return Customer(
            id=customer_model.id,
            business_id=customer_model.business_id,
            name=customer_model.name,
            email=customer_model.email,
            phone_number=customer_model.phone_number,
            address=customer_model.address,
            loyalty_points=customer_model.loyalty_points,
            total_purchases=customer_model.total_purchases,
            created_at=customer_model.created_at,
            updated_at=customer_model.updated_at,
        )


class CustomerPurchaseHistoryRepositoryImpl(CustomerPurchaseHistoryRepository):
    """Django implementation of CustomerPurchaseHistoryRepository."""

    def get_by_customer(
        self, customer_id: UUID, limit: int = 100
    ) -> list[CustomerPurchaseHistory]:
        """Get purchase history for a customer."""
        history = (
            CustomerPurchaseHistoryModel.objects.filter(customer_id=customer_id)
            .select_related("business", "invoice")
            .order_by("-purchase_date")[:limit]
        )
        return [self._to_entity(record) for record in history]

    def create(
        self, history: CustomerPurchaseHistory
    ) -> CustomerPurchaseHistory:
        """Create a new purchase history record."""
        history_model = CustomerPurchaseHistoryModel(
            id=history.id,
            customer_id=history.customer_id,
            business_id=history.business_id,
            invoice_id=history.invoice_id,
            total_amount=history.total_amount,
            purchase_date=history.purchase_date,
        )
        history_model.save()
        return self._to_entity(history_model)

    def _to_entity(
        self, history_model: CustomerPurchaseHistoryModel
    ) -> CustomerPurchaseHistory:
        """Convert Django model to domain entity."""
        return CustomerPurchaseHistory(
            id=history_model.id,
            customer_id=history_model.customer_id,
            business_id=history_model.business_id,
            invoice_id=history_model.invoice_id,
            total_amount=history_model.total_amount,
            purchase_date=history_model.purchase_date,
            created_at=history_model.created_at,
        )

