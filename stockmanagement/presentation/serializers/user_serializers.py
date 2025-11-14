from __future__ import annotations

import re
from urllib.parse import unquote

from rest_framework import serializers

from application.dto.user_dto import (
    ForgotPasswordDTO,
    GoogleOAuthAuthURLDTO,
    GoogleOAuthCodeDTO,
    GoogleOAuthDTO,
    LoginDTO,
    LogoutDTO,
    OTPRequestDTO,
    OTPVerifyDTO,
    ProfileUpdateDTO,
    RefreshTokenDTO,
    ResetPasswordDTO,
    UserCreateDTO,
    UserResponseDTO,
)
from domain.users.entities import UserRole
from infrastructure.persistence.repositories import UserRepositoryImpl
from shared.rate_limiting.decorators import get_client_ip
from shared.utils.device import get_or_detect_device_type


def validate_password_strength(value: str) -> str:
    """
    Validate password strength.

    Args:
        value: Password to validate

    Returns:
        Validated password

    Raises:
        serializers.ValidationError: If password doesn't meet requirements
    """
    if len(value) < 8:
        raise serializers.ValidationError("Password must be at least 8 characters long") from None

    if not re.search(r"[A-Z]", value):
        raise serializers.ValidationError(
            "Password must contain at least one uppercase letter"
        ) from None

    if not re.search(r"[a-z]", value):
        raise serializers.ValidationError(
            "Password must contain at least one lowercase letter"
        ) from None

    if not re.search(r"[0-9]", value):
        raise serializers.ValidationError("Password must contain at least one number") from None

    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', value):
        raise serializers.ValidationError(
            "Password must contain at least one special " "character (!@#$%^&*()_+-=[]{}|;:,.<>?)"
        ) from None

    return value


def validate_phone_number_format(value: str, check_uniqueness: bool = False) -> str | None:
    """
    Validate phone number in E.164 format.

    Args:
        value: Phone number to validate
        check_uniqueness: Whether to check if phone number already exists

    Returns:
        Cleaned phone number or None if empty

    Raises:
        serializers.ValidationError: If phone number is invalid or exists
    """
    if not value or not value.strip():
        return value

    # Remove spaces, dashes, and parentheses
    cleaned = re.sub(r"[\s\-\(\)]", "", value.strip())

    if not re.match(r"^\+[1-9]\d{4,14}$", cleaned):
        raise serializers.ValidationError(
            "Phone number must be in E.164 format "
            "(e.g., +1234567890, +33612345678). "
            "It must start with + followed by country code and number "
            "(4-15 digits total)."
        ) from None

    if check_uniqueness:
        existing_user = UserRepositoryImpl().get_by_phone_number(cleaned)
        if existing_user:
            raise serializers.ValidationError(
                "A user with this phone number already exists. "
                "Please use a different phone number or login."
            ) from None

    return cleaned


def validate_email_or_phone_number(attrs: dict) -> None:
    """
    Validate that exactly one of email or phone_number is provided.

    Args:
        attrs: Dictionary of validated attributes

    Raises:
        serializers.ValidationError: If both or neither are provided
    """
    email = attrs.get("email")
    phone_number = attrs.get("phone_number")

    if not email and not phone_number:
        raise serializers.ValidationError("Either email or phone_number must be provided") from None

    if email and phone_number:
        raise serializers.ValidationError(
            "Provide either email or phone_number, not both"
        ) from None


class UserCreateSerializer(serializers.Serializer):
    """Serializer for user creation with strict validation."""

    email = serializers.EmailField(required=False, allow_blank=True)
    name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        required=True,
        help_text="Password must be at least 8 characters long.",
    )
    confirm_password = serializers.CharField(
        write_only=True,
        min_length=8,
        required=True,
        help_text="Password confirmation - must match password.",
    )
    phone_number = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        help_text="Phone number in international format.",
    )
    role = serializers.ChoiceField(
        choices=[role.value for role in UserRole if role != UserRole.MANAGER],
        default=UserRole.CUSTOMER.value,
        required=False,
    )
    address = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )

    def validate_email(self, value):
        """Validate email format and check for uniqueness."""
        if not value or not value.strip():
            return None

        email = value.strip().lower()

        existing_user = UserRepositoryImpl().get_by_email(email)
        if existing_user:
            raise serializers.ValidationError(
                "A user with this email already exists. Please use a different email or login."
            ) from None

        return email

    def validate_name(self, value):
        """Validate name format if provided."""
        if value:
            value = value.strip()
            if len(value) < 2:
                raise serializers.ValidationError(
                    "Name must be at least 2 characters long"
                ) from None
        return value.strip() if value else None

    def validate_password(self, value):
        """Validate password strength."""
        return validate_password_strength(value)

    def validate_phone_number(self, value):
        """Validate phone number in E.164 format."""
        return validate_phone_number_format(value, check_uniqueness=True)

    def validate(self, attrs):
        """Validate serializer data."""
        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")

        if password and confirm_password:
            if password != confirm_password:
                raise serializers.ValidationError(
                    {"confirm_password": "Passwords do not match"}
                ) from None

        validate_email_or_phone_number(attrs)

        # Role validation - users cannot signup as manager
        if attrs.get("role") == UserRole.MANAGER.value:
            raise serializers.ValidationError("Users cannot signup with manager role") from None
        return attrs

    def to_dto(self) -> UserCreateDTO:
        """Convert to DTO."""
        name = self.validated_data.get("name")
        if not name:
            email = self.validated_data.get("email")
            if email:
                name = email.split("@")[0]
            else:
                phone_number = self.validated_data.get("phone_number")
                if phone_number:
                    name = f"user_{phone_number[-4:]}"
                else:
                    name = "user"

        return UserCreateDTO(
            email=self.validated_data.get("email"),
            name=name,
            password=self.validated_data.get("password"),
            phone_number=self.validated_data.get("phone_number"),
            role=UserRole(self.validated_data.get("role", UserRole.CUSTOMER.value)),
            address=self.validated_data.get("address"),
        )


class LoginSerializer(serializers.Serializer):
    """Serializer for login - supports email+password or phone+password."""

    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(max_length=30, required=False)
    password = serializers.CharField(
        write_only=True,
        required=True,
        help_text="Password is required for login.",
    )
    device_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    device_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    device_type = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate(self, attrs):
        """Validate that either email or phone_number is provided."""
        validate_email_or_phone_number(attrs)
        if not attrs.get("password"):
            raise serializers.ValidationError("Password is required") from None
        return attrs

    def to_dto(self, request) -> LoginDTO:
        """Convert to DTO."""
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        provided_device_type = self.validated_data.get("device_type")
        device_type = get_or_detect_device_type(provided_device_type, user_agent)

        return LoginDTO(
            email=self.validated_data.get("email"),
            phone_number=self.validated_data.get("phone_number"),
            password=self.validated_data.get("password"),
            device_id=self.validated_data.get("device_id"),
            device_name=self.validated_data.get("device_name"),
            device_type=device_type,
            ip_address=get_client_ip(request),
            user_agent=user_agent,
        )


class RefreshTokenSerializer(serializers.Serializer):
    """Serializer for refresh token."""

    refresh_token = serializers.CharField(required=True)
    device_id = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def to_dto(self) -> RefreshTokenDTO:
        """Convert to DTO."""
        return RefreshTokenDTO(
            refresh_token=self.validated_data["refresh_token"],
            device_id=self.validated_data.get("device_id"),
        )


class LogoutSerializer(serializers.Serializer):
    """Serializer for logout.

    Supports three logout modes:
    1. logout_all_devices=True: Logout from all devices
    2. device_id provided: Logout from specific device
    3. Neither provided: Logout from current session only
    """

    device_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Optional: Device ID to logout from a specific device",
    )
    logout_all_devices = serializers.BooleanField(
        default=False,
        help_text="Set to true to logout from all devices. Takes precedence over device_id.",
    )

    def to_dto(self) -> LogoutDTO:
        """Convert to DTO."""
        return LogoutDTO(
            device_id=self.validated_data.get("device_id"),
            logout_all_devices=self.validated_data.get("logout_all_devices", False),
        )


class OTPRequestSerializer(serializers.Serializer):
    """Serializer for OTP request."""

    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(max_length=30, required=False)

    def validate(self, attrs):
        """Validate that either email or phone_number is provided."""
        validate_email_or_phone_number(attrs)
        return attrs

    def to_dto(self) -> OTPRequestDTO:
        """Convert to DTO."""
        return OTPRequestDTO(
            email=self.validated_data.get("email"),
            phone_number=self.validated_data.get("phone_number"),
        )


class OTPVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification - returns tokens after verification."""

    otp = serializers.CharField(required=True, max_length=6, min_length=6)
    device_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    device_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    device_type = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_otp(self, value):
        """Validate OTP code format."""
        if not value or not value.strip():
            raise serializers.ValidationError("OTP code cannot be empty") from None

        if not value.isdigit():
            raise serializers.ValidationError("OTP code must contain only digits") from None
        return value.strip()

    def to_dto(self) -> OTPVerifyDTO:
        """Convert to DTO."""
        return OTPVerifyDTO(
            otp=self.validated_data["otp"],
            email=None,
            phone_number=None,
            otp_type="email",
        )


class GoogleOAuthAuthURLSerializer(serializers.Serializer):
    """Serializer for Google OAuth auth URL request."""

    def to_dto(self) -> GoogleOAuthAuthURLDTO:
        """Convert to DTO."""
        return GoogleOAuthAuthURLDTO()


class GoogleOAuthCodeSerializer(serializers.Serializer):
    """Serializer for Google OAuth code exchange."""

    code = serializers.CharField(required=True, max_length=500)
    device_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    device_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    device_type = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_code(self, value):
        """Validate code is not empty and properly formatted."""
        if not value or not value.strip():
            raise serializers.ValidationError("Code cannot be empty")
        code = value.strip()

        try:
            code = unquote(code)
        except Exception:
            pass
        return code

    def to_dto(self, request) -> GoogleOAuthCodeDTO:
        """Convert to DTO."""
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        provided_device_type = self.validated_data.get("device_type")
        device_type = get_or_detect_device_type(provided_device_type, user_agent)

        return GoogleOAuthCodeDTO(
            code=self.validated_data.get("code"),
            device_id=self.validated_data.get("device_id"),
            device_name=self.validated_data.get("device_name"),
            device_type=device_type,
            ip_address=get_client_ip(request),
            user_agent=user_agent,
        )


class GoogleOAuthSerializer(serializers.Serializer):
    """Serializer for Google OAuth (legacy - for backward compatibility)."""

    access_token = serializers.CharField(required=True)
    device_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    device_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    device_type = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def to_dto(self, request) -> GoogleOAuthDTO:
        """Convert to DTO."""
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        provided_device_type = self.validated_data.get("device_type")
        device_type = get_or_detect_device_type(provided_device_type, user_agent)

        return GoogleOAuthDTO(
            access_token=self.validated_data.get("access_token"),
            device_id=self.validated_data.get("device_id"),
            device_name=self.validated_data.get("device_name"),
            device_type=device_type,
            ip_address=get_client_ip(request),
            user_agent=user_agent,
        )


class ForgotPasswordSerializer(serializers.Serializer):
    """Serializer for forgot password request with strict validation."""

    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(
        max_length=30, required=False, help_text="Phone number in international format"
    )

    def validate_email(self, value):
        """Validate email format."""
        if value:
            return value.strip().lower()
        return value

    def validate_phone_number(self, value):
        """Validate phone number in E.164 format."""
        return validate_phone_number_format(value, check_uniqueness=False)

    def validate(self, attrs):
        """Validate that either email or phone_number is provided."""
        validate_email_or_phone_number(attrs)
        return attrs

    def to_dto(self) -> ForgotPasswordDTO:
        """Convert to DTO."""
        email = self.validated_data.get("email")
        phone_number = self.validated_data.get("phone_number")
        reset_type = "email" if email else "sms"

        return ForgotPasswordDTO(
            email=email,
            phone_number=phone_number,
            reset_type=reset_type,
        )


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for reset password request."""

    token = serializers.CharField(
        max_length=255, required=False, allow_blank=True, help_text="Token for email reset"
    )
    code = serializers.CharField(
        max_length=6, required=False, allow_blank=True, help_text="Code for SMS reset"
    )
    new_password = serializers.CharField(
        write_only=True, min_length=8, required=True, help_text="New password"
    )
    confirm_new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        required=True,
        help_text="Confirm new password (must match new_password)",
    )

    def validate_new_password(self, value):
        """Validate password strength."""
        return validate_password_strength(value)

    def validate(self, attrs):
        """Validate reset password data."""
        token = attrs.get("token", "").strip() if attrs.get("token") else ""
        code = attrs.get("code", "").strip() if attrs.get("code") else ""
        new_password = attrs.get("new_password")
        confirm_new_password = attrs.get("confirm_new_password")

        if not token and not code:
            raise serializers.ValidationError(
                "Either token (for email reset) or code (for SMS reset) must be provided"
            ) from None

        if token and code:
            raise serializers.ValidationError("Provide either token or code, not both") from None

        # Validate password confirmation
        if new_password and confirm_new_password:
            if new_password != confirm_new_password:
                raise serializers.ValidationError(
                    {"confirm_new_password": "Passwords do not match"}
                ) from None

        return attrs

    def to_dto(self) -> ResetPasswordDTO:
        """Convert to DTO."""
        token = (
            self.validated_data.get("token", "").strip()
            if self.validated_data.get("token")
            else None
        )
        code = (
            self.validated_data.get("code", "").strip() if self.validated_data.get("code") else None
        )

        return ResetPasswordDTO(
            token=token if token else None,
            code=code if code else None,
            new_password=self.validated_data["new_password"],
        )


class ProfileUpdateSerializer(serializers.Serializer):
    """Serializer for profile update with validation."""

    name = serializers.CharField(
        max_length=150,
        required=False,
        min_length=2,
        allow_blank=True,
        help_text="User's display name (must be at least 2 characters)",
    )
    phone_number = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        help_text="Phone number in international format",
    )
    address = serializers.CharField(required=False, allow_blank=True, max_length=500)
    avatar_url = serializers.URLField(
        max_length=500, required=False, allow_blank=True, help_text="URL to user avatar image"
    )

    def validate_name(self, value):
        """Validate name format."""
        if value:
            value = value.strip()
            if len(value) < 2:
                raise serializers.ValidationError(
                    "Name must be at least 2 characters long"
                ) from None
        return value.strip() if value else None

    def validate_phone_number(self, value):
        """Validate phone number in E.164 format."""
        return validate_phone_number_format(value, check_uniqueness=False)

    def to_dto(self) -> ProfileUpdateDTO:
        """Convert to DTO."""
        return ProfileUpdateDTO(
            name=self.validated_data.get("name"),
            phone_number=self.validated_data.get("phone_number"),
            address=self.validated_data.get("address"),
            avatar_url=self.validated_data.get("avatar_url"),
        )


class UserResponseSerializer(serializers.Serializer):
    """Serializer for user response data (from UserResponseDTO)."""

    id = serializers.UUIDField()
    email = serializers.EmailField()
    name = serializers.CharField()
    role = serializers.CharField()
    is_active = serializers.BooleanField()
    email_verified = serializers.BooleanField()
    is_staff = serializers.BooleanField()
    is_superuser = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    phone_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    last_login = serializers.DateTimeField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    avatar_url = serializers.URLField(required=False, allow_null=True, allow_blank=True)

    @classmethod
    def from_dto(cls, dto: UserResponseDTO) -> dict:
        """
        Convert UserResponseDTO to serialized dictionary.

        This method takes a DTO from the application layer and converts it
        to a dictionary suitable for JSON API responses.

        Args:
            dto: UserResponseDTO from use case

        Returns:
            Dictionary with serialized user data (ready for JSON response)
        """
        serializer = cls(
            {
                "id": str(dto.id),
                "email": dto.email,
                "name": dto.name,
                "role": dto.role,
                "is_active": dto.is_active,
                "email_verified": dto.email_verified,
                "is_staff": dto.is_staff,
                "is_superuser": dto.is_superuser,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
                "phone_number": dto.phone_number,
                "last_login": dto.last_login,
                "address": dto.address,
                "avatar_url": dto.avatar_url,
            }
        )
        return serializer.data
