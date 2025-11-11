"""User serializers."""

from __future__ import annotations

import re
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
)
from domain.users.entities import UserRole
from shared.rate_limiting.decorators import get_client_ip
from shared.utils.device import get_or_detect_device_type


class UserCreateSerializer(serializers.Serializer):
    """Serializer for user creation with strict validation."""

    email = serializers.EmailField(required=True)
    name = serializers.CharField(
        max_length=150, 
        required=False,
        allow_blank=True,
        help_text="Optional: User's display name. If not provided, will be generated from email"
    )
    password = serializers.CharField(
        write_only=True, 
        min_length=8, 
        required=True,
        help_text="Password must be at least 8 characters long."
    )
    confirm_password = serializers.CharField(
        write_only=True,
        min_length=8,
        required=True,
        help_text="Password confirmation - must match password."
    )
    phone_number = serializers.CharField(
        max_length=30, 
        required=False, 
        allow_blank=True,
        help_text="Phone number in international format."
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
            raise serializers.ValidationError("Email cannot be empty")
        
        email = value.strip().lower()
        
        # Check if email already exists in database
        from infrastructure.persistence.repositories import UserRepositoryImpl
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
        import re
        
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters long"
            ) from None
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError(
                "Password must contain at least one uppercase letter"
            ) from None
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError(
                "Password must contain at least one lowercase letter"
            ) from None
        
        # Check for at least one number
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError(
                "Password must contain at least one number"
            ) from None 
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', value):
            raise serializers.ValidationError(
                "Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)"
            ) from None
        
        return value
    
    def validate_phone_number(self, value):
        """Validate phone number in E.164 format.
        
        E.164 format: +[country code][number]
        - Must start with +
        - Country code: 1-3 digits
        - Number: 4-15 digits total (including country code)
        - Total length: max 15 digits after +
        Example: +1234567890, +33612345678, +221701234567
        """
        if not value or not value.strip():
            return value  # Optional field

        # Remove spaces, dashes, and parentheses
        cleaned = re.sub(r'[\s\-\(\)]', '', value.strip())
        
        # E.164 format: + followed by 1-15 digits
        # Must start with + and country code (1-3 digits), then subscriber number
        if not re.match(r'^\+[1-9]\d{4,14}$', cleaned):
            raise serializers.ValidationError(
                "Phone number must be in E.164 format (e.g., +1234567890, +33612345678). "
                "It must start with + followed by country code and number (4-15 digits total)."
            ) from None
        
        # Check if phone number already exists in database
        from infrastructure.persistence.repositories import UserRepositoryImpl
        existing_user = UserRepositoryImpl().get_by_phone_number(cleaned)
        if existing_user:
            raise serializers.ValidationError(
                "A user with this phone number already exists. Please use a different phone number or login."
            ) from None
        
        return cleaned

    def validate(self, attrs):
        """Validate serializer data."""
        # Validate password and confirm_password match
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise serializers.ValidationError({
                    'confirm_password': 'Passwords do not match'
                }) from None
        
        # Ensure either email or phone_number is provided
        email = attrs.get('email')
        phone_number = attrs.get('phone_number')
        
        if not email and not phone_number:
            raise serializers.ValidationError(
                "Either email or phone_number must be provided"
            ) from None
        
        # Role validation - users cannot signup as manager
        if attrs.get("role") == UserRole.MANAGER.value:
            raise serializers.ValidationError(
                "Users cannot signup with manager role"
            ) from None
        return attrs

    def to_dto(self) -> UserCreateDTO:
        """Convert to DTO."""
        # Generate name from email if not provided
        name = self.validated_data.get("name")
        if not name:
            email = self.validated_data.get("email")
            if not email:
                raise serializers.ValidationError(
                    "Email is required to generate name"
                ) from None
            name = email.split("@")[0]  # Use part before @ as name
        
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
        if not attrs.get("email") and not attrs.get("phone_number"):
            raise serializers.ValidationError(
                "Either email or phone_number must be provided"
            ) from None
        if attrs.get("email") and attrs.get("phone_number"):
            raise serializers.ValidationError(
                "Provide either email or phone_number, not both"
            ) from None 
        if not attrs.get("password"):
            raise serializers.ValidationError(
                "Password is required"
            ) from None
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
    otp_type = serializers.ChoiceField(
        choices=["email", "sms"], default="email", required=False
    )

    def validate(self, attrs):
        """Validate that either email or phone_number is provided."""
        if not attrs.get("email") and not attrs.get("phone_number"):
            raise serializers.ValidationError(
                "Either email or phone_number must be provided"
            ) from None
        return attrs

    def to_dto(self) -> OTPRequestDTO:
        """Convert to DTO."""
        return OTPRequestDTO(
            email=self.validated_data.get("email"),
            phone_number=self.validated_data.get("phone_number"),
            otp_type=self.validated_data.get("otp_type", "email"),
        )

class OTPVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification - returns tokens after verification."""

    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(max_length=30, required=False)
    otp = serializers.CharField(required=True, max_length=6)
    otp_type = serializers.ChoiceField(
        choices=["email", "sms"], default="email", required=False
    )
    device_id = serializers.CharField(max_length=255, required=False, allow_blank=True)
    device_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    device_type = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate(self, attrs):
        """Validate that either email or phone_number is provided."""
        if not attrs.get("email") and not attrs.get("phone_number"):
            raise serializers.ValidationError(
                "Either email or phone_number must be provided"
            ) from None
        return attrs

    def to_dto(self) -> OTPVerifyDTO:
        """Convert to DTO."""
        return OTPVerifyDTO(
            otp=self.validated_data["otp"],
            email=self.validated_data.get("email"),
            phone_number=self.validated_data.get("phone_number"),
            otp_type=self.validated_data.get("otp_type", "email"),
        )


class GoogleOAuthAuthURLSerializer(serializers.Serializer):
    """Serializer for Google OAuth auth URL request.

    Note: Purpose (signup/login) is auto-detected during callback based on whether user exists.
    No parameters required - just call GET /api/v1/auth/google/auth-url/
    """

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
        # URL decode if needed (Google may send URL-encoded code)
        code = value.strip()
        # Remove any URL encoding if present
        from urllib.parse import unquote
        try:
            code = unquote(code)
        except Exception:
            pass  # If unquote fails, use original code
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
        max_length=30, 
        required=False,
        help_text="Phone number in international format"
    )
    reset_type = serializers.ChoiceField(
        choices=["email", "sms"], 
        default="email", 
        required=False
    )

    def validate_email(self, value):
        """Validate email format."""
        if value:
            return value.strip().lower()
        return value

    def validate_phone_number(self, value):
        """Validate phone number in E.164 format.
        
        E.164 format: +[country code][number]
        - Must start with +
        - Country code: 1-3 digits
        - Number: 4-15 digits total (including country code)
        - Total length: max 15 digits after +
        Example: +1234567890, +33612345678, +221701234567
        """
        if not value or not value.strip():
            return value  # Optional field
        
        import re
        
        # Remove spaces, dashes, and parentheses
        cleaned = re.sub(r'[\s\-\(\)]', '', value.strip())
        
        # E.164 format: + followed by 1-15 digits
        # Must start with + and country code (1-3 digits), then subscriber number
        if not re.match(r'^\+[1-9]\d{4,14}$', cleaned):
            raise serializers.ValidationError(
                "Phone number must be in E.164 format (e.g., +1234567890, +33612345678). "
                "It must start with + followed by country code and number (4-15 digits total)."
            ) from None
        
        return cleaned

    def validate(self, attrs):
        """Validate that either email or phone_number is provided based on reset_type."""
        reset_type = attrs.get("reset_type", "email")
        
        if reset_type == "email":
            if not attrs.get("email"):
                raise serializers.ValidationError(
                    "Email is required for email-based password reset"
                ) from None
        else:  # SMS
            if not attrs.get("phone_number"):
                raise serializers.ValidationError(
                    "Phone number is required for SMS-based password reset"
                ) from None
        
        return attrs

    def to_dto(self) -> ForgotPasswordDTO:
        """Convert to DTO."""
        return ForgotPasswordDTO(
            email=self.validated_data.get("email"),
            phone_number=self.validated_data.get("phone_number"),
            reset_type=self.validated_data.get("reset_type", "email"),
        )


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for reset password request."""

    token = serializers.CharField(max_length=255, required=False, allow_blank=True)
    code = serializers.CharField(max_length=6, required=False, allow_blank=True)
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(max_length=30, required=False)
    new_password = serializers.CharField(
        write_only=True, min_length=8, required=True
    )
    reset_type = serializers.ChoiceField(
        choices=["email", "sms"], default="email", required=False
    )

    def validate_new_password(self, value):
        """Validate password strength."""
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters long"
            ) from None
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError(
                "Password must contain at least one uppercase letter"
            ) from None
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError(
                "Password must contain at least one lowercase letter"
            ) from None 
        
        # Check for at least one number
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError(
                "Password must contain at least one number"
            ) from None
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', value):
            raise serializers.ValidationError(
                "Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)"
            ) from None
        
        return value

    def validate(self, attrs):
        """Validate reset password data."""
        reset_type = attrs.get("reset_type", "email")
        
        if reset_type == "email":
            if not attrs.get("token") or not attrs.get("token").strip():
                raise serializers.ValidationError("Token is required for email reset")
        else:  # SMS
            if not attrs.get("code") or not attrs.get("code").strip():
                raise serializers.ValidationError("Code is required for SMS reset")
            if not attrs.get("email") and not attrs.get("phone_number"):
                raise serializers.ValidationError(
                    "Either email or phone_number must be provided for SMS reset"
                ) from None

        return attrs

    def to_dto(self) -> ResetPasswordDTO:
        """Convert to DTO."""
        return ResetPasswordDTO(
            token=self.validated_data.get("token"),
            code=self.validated_data.get("code"),
            email=self.validated_data.get("email"),
            phone_number=self.validated_data.get("phone_number"),
            new_password=self.validated_data["new_password"],
            reset_type=self.validated_data.get("reset_type", "email"),
        )


class ProfileUpdateSerializer(serializers.Serializer):
    """Serializer for profile update with validation."""

    name = serializers.CharField(
        max_length=150, 
        required=False,
        min_length=2,
        allow_blank=True,
        help_text="User's display name (must be at least 2 characters)"
    )
    phone_number = serializers.CharField(
        max_length=30, 
        required=False, 
        allow_blank=True,
        help_text="Phone number in international format"
    )
    address = serializers.CharField(
        required=False, 
        allow_blank=True,
        max_length=500
    )
    avatar_url = serializers.URLField(
        max_length=500, 
        required=False, 
        allow_blank=True,
        help_text="URL to user avatar image"
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
        """Validate phone number in E.164 format.
        
        E.164 format: +[country code][number]
        - Must start with +
        - Country code: 1-3 digits
        - Number: 4-15 digits total (including country code)
        - Total length: max 15 digits after +
        Example: +1234567890
        """
        if not value or not value.strip():
            if not value or not value.strip():
                import re

                # Remove spaces, dashes, and parentheses
                cleaned = re.sub(r'[\s\-\(\)]', '', value.strip())
                if not cleaned:
                    return value  # Optional field
        # Must start with + and number (4-15 digits)
        if not re.match(r'^\+[1-9]\d{4,14}$', cleaned):
            raise serializers.ValidationError(
                "Phone number must be in E.164 format (e.g., +1234567890). " # +[country code][number] is the format
                "It must start with + followed by number (4-15 digits total).",
            ) from None
        
        return cleaned

    def to_dto(self) -> ProfileUpdateDTO:
        """Convert to DTO."""
        return ProfileUpdateDTO(
            name=self.validated_data.get("name"),
            phone_number=self.validated_data.get("phone_number"),
            address=self.validated_data.get("address"),
            avatar_url=self.validated_data.get("avatar_url"),
        )
