"""User domain repositories (interfaces)."""

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from domain.users.entities import Device, OTP, RefreshToken, Session, User, UserRole


class UserRepository(ABC):
    """User repository interface."""

    @abstractmethod
    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        pass

    @abstractmethod
    def get_by_phone_number(self, phone_number: str) -> Optional[User]:
        """Get user by phone number."""
        pass

    @abstractmethod
    def create(self, user: User, password: Optional[str] = None) -> User:
        """Create a new user."""
        pass

    @abstractmethod
    def update(self, user: User) -> User:
        """Update an existing user."""
        pass

    @abstractmethod
    def delete(self, user_id: UUID) -> None:
        """Delete a user."""
        pass

    @abstractmethod
    def get_by_role(self, role: UserRole) -> list[User]:
        """Get users by role."""
        pass

    @abstractmethod
    def verify_password(self, user_id: UUID, password: str) -> bool:
        """Verify user password."""
        pass


class SessionRepository(ABC):
    """Session repository interface."""

    @abstractmethod
    def get_by_id(self, session_id: UUID) -> Optional[Session]:
        """Get session by ID."""
        pass

    @abstractmethod
    def get_active_sessions_by_user(self, user_id: UUID) -> list[Session]:
        """Get active sessions for a user."""
        pass

    @abstractmethod
    def create(self, session: Session) -> Session:
        """Create a new session."""
        pass

    @abstractmethod
    def update(self, session: Session) -> Session:
        """Update an existing session."""
        pass

    @abstractmethod
    def get_user_sessions(
        self, user_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Session]:
        """Get user session history."""
        pass


class RefreshTokenRepository(ABC):
    """Refresh token repository interface."""

    @abstractmethod
    def get_by_id(self, token_id: UUID) -> Optional[RefreshToken]:
        """Get refresh token by ID."""
        pass

    @abstractmethod
    def get_by_token(self, token: str) -> Optional[RefreshToken]:
        """Get refresh token by token string."""
        pass

    @abstractmethod
    def create(self, refresh_token: RefreshToken) -> RefreshToken:
        """Create a new refresh token."""
        pass

    @abstractmethod
    def update(self, refresh_token: RefreshToken) -> RefreshToken:
        """Update an existing refresh token."""
        pass

    @abstractmethod
    def revoke(self, token_id: UUID) -> None:
        """Revoke a refresh token."""
        pass

    @abstractmethod
    def revoke_all_user_tokens(self, user_id: UUID) -> None:
        """Revoke all refresh tokens for a user."""
        pass

    @abstractmethod
    def revoke_user_device_tokens(self, user_id: UUID, device_id: str) -> None:
        """Revoke refresh tokens for a specific user device."""
        pass


class DeviceRepository(ABC):
    """Device repository interface."""

    @abstractmethod
    def get_by_id(self, device_id: UUID) -> Optional[Device]:
        """Get device by ID."""
        pass

    @abstractmethod
    def get_by_device_id(self, device_id: str) -> Optional[Device]:
        """Get device by device_id string."""
        pass

    @abstractmethod
    def create(self, device: Device) -> Device:
        """Create a new device."""
        pass

    @abstractmethod
    def update(self, device: Device) -> Device:
        """Update an existing device."""
        pass

    @abstractmethod
    def delete(self, device_id: UUID) -> None:
        """Delete a device."""
        pass

    @abstractmethod
    def get_user_devices(self, user_id: UUID) -> list[Device]:
        """Get all devices for a user."""
        pass


class OTPRepository(ABC):
    """OTP repository interface."""

    @abstractmethod
    def get_by_id(self, otp_id: UUID) -> Optional[OTP]:
        """Get OTP by ID."""
        pass

    @abstractmethod
    def get_by_code(
        self, code: str, email: Optional[str] = None, phone_number: Optional[str] = None
    ) -> Optional[OTP]:
        """Get OTP by code and identifier."""
        pass

    @abstractmethod
    def get_latest_by_email(
        self, email: str, purpose: str, otp_type: str
    ) -> Optional[OTP]:
        """Get latest OTP by email, purpose, and type."""
        pass

    @abstractmethod
    def get_latest_by_phone(
        self, phone_number: str, purpose: str, otp_type: str
    ) -> Optional[OTP]:
        """Get latest OTP by phone number, purpose, and type."""
        pass

    @abstractmethod
    def create(self, otp: OTP) -> OTP:
        """Create a new OTP."""
        pass

    @abstractmethod
    def update(self, otp: OTP) -> OTP:
        """Update an existing OTP."""
        pass

    @abstractmethod
    def delete(self, otp_id: UUID) -> None:
        """Delete an OTP."""
        pass

    @abstractmethod
    def delete_expired(self) -> int:
        """Delete expired OTPs. Returns count of deleted OTPs."""
        pass

    @abstractmethod
    def invalidate_all_pending(
        self,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
        purpose: Optional[str] = None,
        otp_type: Optional[str] = None,
    ) -> int:
        """Invalidate all pending (non-verified) OTPs for given criteria.
        
        Args:
            email: Email address (optional)
            phone_number: Phone number (optional)
            purpose: Purpose of OTP (optional)
            otp_type: Type of OTP (optional)
            
        Returns:
            Number of OTPs invalidated
        """
        pass
