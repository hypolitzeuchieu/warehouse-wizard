"""Business serializers."""

from rest_framework import serializers

from application.dto.business_dto import (
    BusinessCreateDTO,
    BusinessMemberCreateDTO,
    BusinessUpdateDTO,
)


class BusinessCreateSerializer(serializers.Serializer):
    """Serializer for business creation."""

    name = serializers.CharField(max_length=255, required=True)
    unique_name = serializers.CharField(max_length=100, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    settings = serializers.JSONField(required=False, default=dict)

    def to_dto(self) -> BusinessCreateDTO:
        """Convert to DTO."""
        return BusinessCreateDTO(
            name=self.validated_data["name"],
            unique_name=self.validated_data["unique_name"],
            description=self.validated_data.get("description"),
            address=self.validated_data.get("address"),
            phone_number=self.validated_data.get("phone_number"),
            email=self.validated_data.get("email"),
            settings=self.validated_data.get("settings"),
        )


class BusinessUpdateSerializer(serializers.Serializer):
    """Serializer for business update."""

    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    logo_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    settings = serializers.JSONField(required=False)

    def to_dto(self) -> BusinessUpdateDTO:
        """Convert to DTO."""
        return BusinessUpdateDTO(
            name=self.validated_data.get("name"),
            description=self.validated_data.get("description"),
            address=self.validated_data.get("address"),
            phone_number=self.validated_data.get("phone_number"),
            email=self.validated_data.get("email"),
            logo_url=self.validated_data.get("logo_url"),
            settings=self.validated_data.get("settings"),
        )


class BusinessMemberCreateSerializer(serializers.Serializer):
    """Serializer for adding business member."""

    user_id = serializers.UUIDField(required=True)
    role = serializers.ChoiceField(
        choices=["manager", "cashier", "stock_keeper", "delivery"],
        required=True,
    )

    def to_dto(self) -> BusinessMemberCreateDTO:
        """Convert to DTO."""
        return BusinessMemberCreateDTO(
            user_id=self.validated_data["user_id"],
            role=self.validated_data["role"],
        )

