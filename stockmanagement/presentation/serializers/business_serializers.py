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
from presentation.serializers.user_serializers import validate_password_strength
from shared.utils.upload_validation import validate_max_upload_size


class BusinessCreateSerializer(serializers.Serializer):
    """Serializer for business creation."""

    name = serializers.CharField(max_length=255, required=True)
    description = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(
        max_length=30, required=False, allow_blank=True
    )
    email = serializers.EmailField(required=False, allow_blank=True)
    settings = serializers.JSONField(required=False, default=dict)
    logo = serializers.ImageField(required=False, allow_null=True)
    logo_url = serializers.URLField(max_length=500, required=False, allow_blank=True)

    def validate(self, attrs):
        logo = attrs.get("logo")
        logo_url = attrs.get("logo_url")
        if logo and logo_url:
            raise serializers.ValidationError(
                "Provide either 'logo' or 'logo_url', not both."
            )
        if logo:
            validate_max_upload_size(logo, field_name="logo")
        return attrs

    def to_dto(self) -> BusinessCreateDTO:
        """Convert to DTO."""
        return BusinessCreateDTO(
            name=self.validated_data["name"],
            unique_name=None,
            description=self.validated_data.get("description"),
            address=self.validated_data.get("address"),
            phone_number=self.validated_data.get("phone_number"),
            email=self.validated_data.get("email"),
            settings=self.validated_data.get("settings"),
            logo_file=self.validated_data.get("logo"),
            logo_url=(self.validated_data.get("logo_url") or None),
        )


class BusinessUpdateSerializer(serializers.Serializer):
    """Serializer for business update."""

    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(
        max_length=30, required=False, allow_blank=True
    )
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

    user_id = serializers.UUIDField(required=False, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(
        max_length=30, required=False, allow_blank=True, allow_null=True
    )
    name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, allow_null=True
    )
    password = serializers.CharField(
        write_only=True, min_length=8, required=False, allow_blank=True, allow_null=True
    )
    role = serializers.ChoiceField(
        choices=[
            "manager",
            "cashier",
            "stock_keeper",
            "delivery",
            "partner",
            "wholesaler",
        ],
        required=True,
    )

    def validate(self, attrs):
        """Validate serializer data."""
        user_id = attrs.get("user_id")
        email = attrs.get("email")
        phone_number = attrs.get("phone_number")
        name = attrs.get("name")

        if not user_id and not email and not phone_number:
            raise serializers.ValidationError(
                "Either user_id or email/phone_number must be provided"
            )

        if not user_id and not name:
            raise serializers.ValidationError(
                "Name is required when creating a new user"
            )

        if attrs.get("role") == "owner":
            raise serializers.ValidationError("Cannot create a member with owner role")
        if attrs.get("password"):
            attrs["password"] = validate_password_strength(attrs.get("password"))

        return attrs

    def to_dto(self) -> BusinessMemberCreateDTO:
        """Convert to DTO."""
        return BusinessMemberCreateDTO(
            user_id=self.validated_data.get("user_id"),
            email=self.validated_data.get("email"),
            phone_number=self.validated_data.get("phone_number"),
            name=self.validated_data.get("name"),
            password=self.validated_data.get("password"),
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
        user_data = dto.user if dto.user else None

        return {
            "id": str(dto.id),
            "role": dto.role,
            "is_active": dto.is_active,
            "joined_at": dto.joined_at,
            "left_at": dto.left_at,
            "created_at": dto.created_at,
            "updated_at": dto.updated_at,
            "user": user_data,
        }


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
    subscription = serializers.JSONField(allow_null=True, required=False)
    member_count = serializers.IntegerField(required=False, allow_null=True)
    members = BusinessMemberSerializer(many=True, required=False, allow_null=True)

    @classmethod
    def from_dto(
        cls,
        dto: BusinessResponseDTO,
        members: Sequence[BusinessMemberResponseDTO] | None = None,
        member_count: int | None = None,
    ) -> dict:
        """Convert BusinessResponseDTO to serialized data."""
        if member_count is None and members is not None:
            member_count = len(members)

        serialized_members = (
            [BusinessMemberSerializer.from_dto(member_dto) for member_dto in members]
            if members is not None
            else None
        )

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
                "subscription": dto.subscription,
                "member_count": member_count,
            }
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.data

        if serialized_members is not None:
            data["members"] = serialized_members
        elif "members" in data:
            data.pop("members", None)

        return data


class BusinessIdQuerySerializer(serializers.Serializer):
    """Serializer for validating business_id query parameter."""

    business_id = serializers.UUIDField(required=True, help_text="Business UUID")
