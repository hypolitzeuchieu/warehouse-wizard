"""User DTOs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from domain.users.entities import UserRole


@dataclass
class UserCreateDTO:
    """DTO for creating a user."""

    email: str
    name: Optional[str] = None  # Optional, will be generated from email if not provided
    password: str = ""
    phone_number: Optional[str] = None
    role: UserRole = UserRole.CUSTOMER
    address: Optional[str] = None


@dataclass
class UserUpdateDTO:
    """DTO for updating a user."""

    email: Optional[str] = None
    name: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


@dataclass
class UserResponseDTO:
    """DTO for user response."""

    id: UUID
    email: str
    name: str  # Renamed from username
    role: str
    is_active: bool
    is_staff: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    phone_number: Optional[str] = None
    last_login: Optional[datetime] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None


@dataclass
class LoginDTO:
    """DTO for login request."""

    email: Optional[str] = None
    phone_number: Optional[str] = None
    password: str = ""  # Required for password-based login
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class LoginResponseDTO:
    """DTO for login response."""

    access_token: str
    refresh_token: str
    user: UserResponseDTO
    expires_in: int  # seconds


@dataclass
class RefreshTokenDTO:
    """DTO for refresh token request."""

    refresh_token: str
    device_id: Optional[str] = None


@dataclass
class RefreshTokenResponseDTO:
    """DTO for refresh token response."""

    access_token: str
    refresh_token: str
    expires_in: int


@dataclass
class LogoutDTO:
    """DTO for logout request."""

    device_id: Optional[str] = None
    logout_all_devices: bool = False


@dataclass
class OTPRequestDTO:
    """DTO for OTP request."""

    email: Optional[str] = None
    phone_number: Optional[str] = None
    otp_type: str = "email"  # email or sms


@dataclass
class OTPVerifyDTO:
    """DTO for OTP verification."""

    otp: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    otp_type: str = "email"


@dataclass
class GoogleOAuthAuthURLDTO:
    """DTO for Google OAuth auth URL request."""
    pass


@dataclass
class GoogleOAuthAuthURLResponseDTO:
    """DTO for Google OAuth auth URL response."""

    auth_url: str
    expires_in: int  # seconds


@dataclass
class GoogleOAuthCodeDTO:
    """DTO for Google OAuth code exchange."""

    code: str
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class GoogleOAuthDTO:
    """DTO for Google OAuth (legacy - for backward compatibility)."""

    access_token: str
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class SessionResponseDTO:
    """DTO for session response."""

    id: UUID
    user_id: UUID
    start_time: datetime
    created_at: datetime
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    device_type: Optional[str] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    is_active: bool = True
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class ForgotPasswordDTO:
    """DTO for forgot password request."""

    email: Optional[str] = None
    phone_number: Optional[str] = None
    reset_type: str = "email"  # email or sms


@dataclass
class ResetPasswordDTO:
    """DTO for reset password request."""

    token: Optional[str] = None  # For email reset
    code: Optional[str] = None  # For SMS reset
    email: Optional[str] = None
    phone_number: Optional[str] = None
    new_password: str = ""
    reset_type: str = "email"


@dataclass
class ProfileUpdateDTO:
    """DTO for profile update."""

    name: Optional[str] = None  # Renamed from username
    phone_number: Optional[str] = None
    address: Optional[str] = None
    avatar_url: Optional[str] = None

