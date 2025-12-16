"""User DTOs."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.users.entities import UserRole


@dataclass
class UserCreateDTO:
    """DTO for creating a user."""

    email: str | None = None
    name: str | None = None
    password: str = ""
    phone_number: str | None = None
    role: UserRole = UserRole.CUSTOMER
    address: str | None = None


@dataclass
class SignupResponseDTO:
    """DTO for signup response."""

    message: str
    expires_in_minutes: int
    email: str | None = None
    phone_number: str | None = None
    otp_type: str | None = None


@dataclass
class UserUpdateDTO:
    """DTO for updating a user."""

    email: str | None = None
    name: str | None = None
    phone_number: str | None = None
    address: str | None = None
    is_active: bool | None = None


@dataclass
class UserResponseDTO:
    """DTO for user response."""

    id: UUID
    email: str
    name: str
    role: str
    is_active: bool
    email_verified: bool
    is_staff: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    phone_number: str | None = None
    last_login: datetime | None = None
    address: str | None = None
    avatar_url: str | None = None


@dataclass
class LoginDTO:
    """DTO for login request."""

    email: str | None = None
    phone_number: str | None = None
    password: str = ""
    device_id: str | None = None
    device_name: str | None = None
    device_type: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass
class LoginResponseDTO:
    """DTO for login response."""

    access_token: str
    refresh_token: str
    user: UserResponseDTO
    expires_in: int


@dataclass
class RefreshTokenDTO:
    """DTO for refresh token request."""

    refresh_token: str
    device_id: str | None = None


@dataclass
class RefreshTokenResponseDTO:
    """DTO for refresh token response."""

    access_token: str
    refresh_token: str
    expires_in: int


@dataclass
class LogoutDTO:
    """DTO for logout request."""

    device_id: str | None = None
    logout_all_devices: bool = False


@dataclass
class OTPRequestDTO:
    """DTO for OTP request."""

    email: str | None = None
    phone_number: str | None = None


@dataclass
class OTPVerifyDTO:
    """DTO for OTP verification."""

    otp: str
    email: str | None = None
    phone_number: str | None = None
    otp_type: str = "email"


@dataclass
class GoogleOAuthAuthURLDTO:
    """DTO for Google OAuth auth URL request."""

    pass


@dataclass
class GoogleOAuthAuthURLResponseDTO:
    """DTO for Google OAuth auth URL response."""

    auth_url: str


@dataclass
class GoogleOAuthCodeDTO:
    """DTO for Google OAuth code exchange."""

    code: str
    device_id: str | None = None
    device_name: str | None = None
    device_type: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass
class GoogleOAuthDTO:
    """DTO for Google OAuth (legacy - for backward compatibility)."""

    access_token: str
    device_id: str | None = None
    device_name: str | None = None
    device_type: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass
class SessionResponseDTO:
    """DTO for session response."""

    id: UUID
    user_id: UUID
    start_time: datetime
    created_at: datetime
    device_id: str | None = None
    device_name: str | None = None
    device_type: str | None = None
    end_time: datetime | None = None
    duration_seconds: float | None = None
    is_active: bool = True
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass
class ForgotPasswordDTO:
    """DTO for forgot password request."""

    email: str | None = None
    phone_number: str | None = None
    reset_type: str = "email"  # email or sms


@dataclass
class ResetPasswordDTO:
    """DTO for reset password request."""

    token: str | None = None
    code: str | None = None
    new_password: str = ""


@dataclass
class ProfileUpdateDTO:
    """DTO for profile update."""

    name: str | None = None
    phone_number: str | None = None
    address: str | None = None
    avatar_url: str | None = None
