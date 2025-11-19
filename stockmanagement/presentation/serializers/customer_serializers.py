"""Customer serializers."""

from rest_framework import serializers

from application.dto.customer_dto import (
    CustomerCreateDTO,
    CustomerResponseDTO,
    CustomerUpdateDTO,
)


class CustomerCreateSerializer(serializers.Serializer):
    """Serializer for customer creation."""

    name = serializers.CharField(max_length=255, required=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(
        max_length=30, required=False, allow_blank=True, allow_null=True
    )
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    customer_type = serializers.ChoiceField(
        choices=["REGULAR", "WHOLESALER"], default="REGULAR", required=False
    )

    def to_dto(self) -> CustomerCreateDTO:
        """Convert to DTO."""
        return CustomerCreateDTO(
            name=self.validated_data["name"],
            email=self.validated_data.get("email"),
            phone_number=self.validated_data.get("phone_number"),
            address=self.validated_data.get("address"),
            customer_type=self.validated_data.get("customer_type", "REGULAR"),
        )


class CustomerUpdateSerializer(serializers.Serializer):
    """Serializer for customer update."""

    name = serializers.CharField(max_length=255, required=False)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(
        max_length=30, required=False, allow_blank=True, allow_null=True
    )
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    customer_type = serializers.ChoiceField(choices=["REGULAR", "WHOLESALER"], required=False)

    def to_dto(self) -> CustomerUpdateDTO:
        """Convert to DTO."""
        return CustomerUpdateDTO(
            name=self.validated_data.get("name"),
            email=self.validated_data.get("email"),
            phone_number=self.validated_data.get("phone_number"),
            address=self.validated_data.get("address"),
            customer_type=self.validated_data.get("customer_type"),
        )


class CustomerResponseSerializer(serializers.Serializer):
    """Serializer for customer responses."""

    id = serializers.UUIDField()
    business_id = serializers.UUIDField(allow_null=True, required=False)
    name = serializers.CharField()
    email = serializers.EmailField(allow_null=True, required=False)
    phone_number = serializers.CharField(allow_null=True, required=False)
    address = serializers.CharField(allow_null=True, required=False)
    customer_type = serializers.CharField()
    loyalty_points = serializers.DecimalField(max_digits=18, decimal_places=2)
    total_purchases = serializers.DecimalField(max_digits=18, decimal_places=2)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @classmethod
    def from_dto(cls, dto: CustomerResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "business_id": dto.business_id,
                "name": dto.name,
                "email": dto.email,
                "phone_number": dto.phone_number,
                "address": dto.address,
                "customer_type": dto.customer_type,
                "loyalty_points": dto.loyalty_points,
                "total_purchases": dto.total_purchases,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data
