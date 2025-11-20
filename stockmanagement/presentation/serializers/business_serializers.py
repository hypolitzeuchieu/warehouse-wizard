"""Business serializers."""

from collections.abc import Sequence

from rest_framework import serializers

from application.dto.business_dto import (
    BusinessCreateDTO,
    BusinessMemberCreateDTO,
    BusinessMemberResponseDTO,
    BusinessResponseDTO,
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


class BusinessMemberUserSerializer(serializers.Serializer):
    """Serializer for nested user information on business members."""

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True, allow_blank=True, allow_null=True)
    email = serializers.EmailField(
        read_only=True,
        allow_blank=True,
        allow_null=True,
        required=False,
    )
    phone_number = serializers.CharField(
        read_only=True,
        allow_blank=True,
        allow_null=True,
        required=False,
    )
    role = serializers.CharField(read_only=True, allow_blank=True, allow_null=True)
    avatar_url = serializers.CharField(
        read_only=True,
        allow_blank=True,
        allow_null=True,
        required=False,
    )
    is_active = serializers.BooleanField(read_only=True, required=False)


class BusinessMemberSerializer(serializers.Serializer):
    """Serializer for business member responses."""

    id = serializers.UUIDField(read_only=True)
    business_id = serializers.UUIDField(read_only=True)
    user_id = serializers.UUIDField(read_only=True)
    role = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    joined_at = serializers.DateTimeField(read_only=True)
    left_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    user = BusinessMemberUserSerializer(read_only=True, allow_null=True, required=False)

    @classmethod
    def from_dto(cls, dto: BusinessMemberResponseDTO) -> dict:
        """Convert BusinessMemberResponseDTO to serialized data."""
        serializer = cls(
            data={
                "id": dto.id,
                "business_id": dto.business_id,
                "user_id": dto.user_id,
                "role": dto.role,
                "is_active": dto.is_active,
                "joined_at": dto.joined_at,
                "left_at": dto.left_at,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
                "user": dto.user,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class BusinessResponseSerializer(serializers.Serializer):
    """Serializer for business response DTOs."""

    id = serializers.UUIDField()
    name = serializers.CharField()
    unique_name = serializers.CharField()
    owner_id = serializers.UUIDField()
    description = serializers.CharField(allow_null=True, required=False)
    address = serializers.CharField(allow_null=True, required=False)
    phone_number = serializers.CharField(allow_null=True, required=False)
    email = serializers.EmailField(allow_null=True, required=False)
    qr_code_url = serializers.CharField(allow_null=True, required=False)
    logo_url = serializers.CharField(allow_null=True, required=False)
    is_active = serializers.BooleanField()
    settings = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    members = BusinessMemberSerializer(many=True, required=False, allow_null=True)

    @classmethod
    def from_dto(
        cls,
        dto: BusinessResponseDTO,
        members: Sequence[BusinessMemberResponseDTO] | None = None,
    ) -> dict:
        """Convert BusinessResponseDTO to serialized data."""
        serializer = cls(
            data={
                "id": dto.id,
                "name": dto.name,
                "unique_name": dto.unique_name,
                "owner_id": dto.owner_id,
                "description": dto.description,
                "address": dto.address,
                "phone_number": dto.phone_number,
                "email": dto.email,
                "qr_code_url": dto.qr_code_url,
                "logo_url": dto.logo_url,
                "is_active": dto.is_active,
                "settings": dto.settings,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
                "members": (
                    [BusinessMemberSerializer.from_dto(member_dto) for member_dto in members]
                    if members is not None
                    else None
                ),
            }
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.data
        if serializer.initial_data.get("members") is None:
            data.pop("members", None)
        return data
