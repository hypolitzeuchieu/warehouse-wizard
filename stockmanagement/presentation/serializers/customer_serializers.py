"""Customer serializers."""

from rest_framework import serializers

from application.dto.customer_dto import (
    CustomerCreateDTO,
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
