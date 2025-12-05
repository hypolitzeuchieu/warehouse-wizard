"""Customer use cases."""

from uuid import UUID, uuid4

from django.utils import timezone

from application.dto.customer_dto import (
    CustomerCreateDTO,
    CustomerResponseDTO,
    CustomerUpdateDTO,
)
from domain.business.services import BusinessDomainService
from domain.customer.entities import Customer, CustomerType
from domain.customer.repositories import CustomerRepository
from shared.exceptions.specific import (
    BadRequestError,
)
from shared.utils.validation import (
    validate_business_access,
    validate_entity_belongs_to_business,
)


def _validate_customer_email_phone_uniqueness(
    customer_repository: CustomerRepository,
    email: str | None,
    phone_number: str | None,
    business_id: UUID,
    exclude_customer_id: UUID | None = None,
) -> None:
    """
    Validate that customer email/phone doesn't already exist.

    Shared utility function to avoid code duplication.

    Args:
        customer_repository: Customer repository
        email: Email to validate
        phone_number: Phone number to validate
        business_id: Business ID
        exclude_customer_id: Optional customer ID to exclude from check (for updates)

    Raises:
        BadRequestError: If email/phone already exists
    """
    if email:
        existing = customer_repository.get_by_email(email, business_id)
        if existing and (exclude_customer_id is None or existing.id != exclude_customer_id):
            raise BadRequestError(
                detail="Customer with this email already exists",
                code="CUSTOMER_EXISTS",
            )

    if phone_number:
        existing = customer_repository.get_by_phone(phone_number, business_id)
        if existing and (exclude_customer_id is None or existing.id != exclude_customer_id):
            raise BadRequestError(
                detail="Customer with this phone number already exists",
                code="CUSTOMER_EXISTS",
            )


def _customer_to_dto(customer: Customer) -> CustomerResponseDTO:
    """Convert customer entity to DTO (shared utility function)."""
    return CustomerResponseDTO(
        id=customer.id,
        business_id=customer.business_id,
        name=customer.name,
        email=customer.email,
        phone_number=customer.phone_number,
        address=customer.address,
        customer_type=customer.customer_type.value,
        loyalty_points=customer.loyalty_points,
        total_purchases=customer.total_purchases,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


class CreateCustomerUseCase:
    """Use case for creating a customer."""

    def __init__(
        self,
        customer_repository: CustomerRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.customer_repository = customer_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: CustomerCreateDTO) -> CustomerResponseDTO:
        """Execute customer creation."""
        # Check if user has access to business
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        # Check if customer with email/phone already exists
        _validate_customer_email_phone_uniqueness(
            customer_repository=self.customer_repository,
            email=dto.email,
            phone_number=dto.phone_number,
            business_id=self.business_id,
        )

        # Create customer entity
        customer = Customer(
            id=uuid4(),
            business_id=self.business_id,
            name=dto.name,
            email=dto.email,
            phone_number=dto.phone_number,
            address=dto.address,
            customer_type=CustomerType(dto.customer_type),
            loyalty_points=0,
            total_purchases=0,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        customer = self.customer_repository.create(customer)
        return self._to_dto(customer)

    def _to_dto(self, customer: Customer) -> CustomerResponseDTO:
        """Convert customer entity to DTO."""
        return _customer_to_dto(customer)


class GetCustomerUseCase:
    """Use case for getting a customer by ID."""

    def __init__(
        self,
        customer_repository: CustomerRepository,
        business_domain_service: BusinessDomainService,
        customer_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.customer_repository = customer_repository
        self.business_domain_service = business_domain_service
        self.customer_id = customer_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self) -> CustomerResponseDTO:
        """Execute getting customer."""
        # Check if user has access to business
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        customer = self.customer_repository.get_by_id(self.customer_id)
        validate_entity_belongs_to_business(
            entity=customer,
            business_id=self.business_id,
            entity_name="Customer",
        )

        return self._to_dto(customer)

    def _to_dto(self, customer: Customer) -> CustomerResponseDTO:
        """Convert customer entity to DTO."""
        return _customer_to_dto(customer)


class ListCustomersUseCase:
    """Use case for listing customers for a business."""

    def __init__(
        self,
        customer_repository: CustomerRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        limit: int = 100,
    ) -> None:
        """Initialize use case."""
        self.customer_repository = customer_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.limit = limit

    def execute(self) -> list[CustomerResponseDTO]:
        """Execute listing customers."""
        # Check if user has access to business
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        customers = self.customer_repository.get_by_business(self.business_id, limit=self.limit)
        return [self._to_dto(customer) for customer in customers]

    def _to_dto(self, customer: Customer) -> CustomerResponseDTO:
        """Convert customer entity to DTO."""
        return _customer_to_dto(customer)


class UpdateCustomerUseCase:
    """Use case for updating a customer."""

    def __init__(
        self,
        customer_repository: CustomerRepository,
        business_domain_service: BusinessDomainService,
        customer_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.customer_repository = customer_repository
        self.business_domain_service = business_domain_service
        self.customer_id = customer_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, dto: CustomerUpdateDTO) -> CustomerResponseDTO:
        """Execute customer update."""
        # Check if user has access to business
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        customer = self.customer_repository.get_by_id(self.customer_id)
        validate_entity_belongs_to_business(
            entity=customer,
            business_id=self.business_id,
            entity_name="Customer",
        )

        # Update fields
        if dto.name is not None:
            customer.name = dto.name
        if dto.email is not None:
            # Check if email already exists for another customer
            _validate_customer_email_phone_uniqueness(
                customer_repository=self.customer_repository,
                email=dto.email,
                phone_number=None,
                business_id=self.business_id,
                exclude_customer_id=customer.id,
            )
            customer.email = dto.email
        if dto.phone_number is not None:
            # Check if phone already exists for another customer
            _validate_customer_email_phone_uniqueness(
                customer_repository=self.customer_repository,
                email=None,
                phone_number=dto.phone_number,
                business_id=self.business_id,
                exclude_customer_id=customer.id,
            )
            customer.phone_number = dto.phone_number
        if dto.address is not None:
            customer.address = dto.address
        if dto.customer_type is not None:
            customer.customer_type = CustomerType(dto.customer_type)

        customer.updated_at = timezone.now()
        customer = self.customer_repository.update(customer)
        return self._to_dto(customer)

    def _to_dto(self, customer: Customer) -> CustomerResponseDTO:
        """Convert customer entity to DTO."""
        return _customer_to_dto(customer)


class DeleteCustomerUseCase:
    """Use case for deleting a customer."""

    def __init__(
        self,
        customer_repository: CustomerRepository,
        business_domain_service: BusinessDomainService,
        customer_id: UUID,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.customer_repository = customer_repository
        self.business_domain_service = business_domain_service
        self.customer_id = customer_id
        self.business_id = business_id
        self.user_id = user_id

    def execute(self) -> None:
        """Execute customer deletion."""
        # Check if user has access to business
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        customer = self.customer_repository.get_by_id(self.customer_id)
        validate_entity_belongs_to_business(
            entity=customer,
            business_id=self.business_id,
            entity_name="Customer",
        )

        self.customer_repository.delete(self.customer_id)
