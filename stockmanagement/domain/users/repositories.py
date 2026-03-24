"""User domain repositories (interfaces)."""

from abc import ABC, abstractmethod
from uuid import UUID

from domain.users.entities import (
    OTP,
    Device,
    PasswordResetToken,
    RefreshToken,
    Session,
    User,
    UserRole,
)


class UserRepository(ABC):
    """User repository interface."""

    @abstractmethod
    def get_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        pass

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        pass

    @abstractmethod
    def get_by_phone_number(self, phone_number: str) -> User | None:
        """Get user by phone number."""
        pass

    @abstractmethod
    def get_by_google_id(self, google_id: str) -> User | None:
        """Get user by Google ID."""
        pass

    @abstractmethod
    def create(self, user: User, password: str | None = None) -> User:
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

    @abstractmethod
    def update_password(self, user_id: UUID, new_password: str) -> User:
        """Update user password."""
        pass

    @abstractmethod
    def search(
        self,
        email: str | None = None,
        phone_number: str | None = None,
        name: str | None = None,
        search_query: str | None = None,
    ) -> list[User]:
        """
        Search for users by email, phone number, or name.
        Returns all users if no search parameters are provided.

        Args:
            email: Exact email to search for
            phone_number: Exact phone number to search for
            name: Partial name match
            search_query: General query that searches in email, phone, and name

        Returns:
            List of User entities matching the search criteria, or all users if no parameters provided
        """
        pass


class SessionRepository(ABC):
    """Session repository interface."""

    @abstractmethod
    def get_by_id(self, session_id: UUID) -> Session | None:
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
    def get_user_sessions(self, user_id: UUID, limit: int = 100, offset: int = 0) -> list[Session]:
        """Get user session history."""
        pass


class RefreshTokenRepository(ABC):
    """Refresh token repository interface."""

    @abstractmethod
    def get_by_id(self, token_id: UUID) -> RefreshToken | None:
        """Get refresh token by ID."""
        pass

    @abstractmethod
    def get_by_token(self, token: str) -> RefreshToken | None:
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
    def get_by_id(self, device_id: UUID) -> Device | None:
        """Get device by ID."""
        pass

    @abstractmethod
    def get_by_device_id(self, device_id: str) -> Device | None:
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
    def get_by_id(self, otp_id: UUID) -> OTP | None:
        """Get OTP by ID."""
        pass

    @abstractmethod
    def get_by_code(
        self, code: str, email: str | None = None, phone_number: str | None = None
    ) -> OTP | None:
        """Get OTP by code and identifier."""
        pass

    @abstractmethod
    def get_latest_by_email(self, email: str, otp_type: str) -> OTP | None:
        """Get latest OTP by email and type."""
        pass

    @abstractmethod
    def get_latest_by_phone(self, phone_number: str, otp_type: str) -> OTP | None:
        """Get latest OTP by phone number and type."""
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
        email: str | None = None,
        phone_number: str | None = None,
        otp_type: str | None = None,
    ) -> int:
        """Invalidate all pending (non-verified) OTPs for given criteria.

        Args:
            email: Email address (optional)
            phone_number: Phone number (optional)
            otp_type: Type of OTP (optional)

        Returns:
            Number of OTPs invalidated
        """
        pass


class PasswordResetTokenRepository(ABC):
    """Password reset token repository interface."""

    @abstractmethod
    def get_by_id(self, token_id: UUID) -> PasswordResetToken | None:
        """Get password reset token by ID."""
        pass

    @abstractmethod
    def get_by_token(self, token: str) -> PasswordResetToken | None:
        """Get password reset token by token string."""
        pass

    @abstractmethod
    def get_by_code(self, code: str) -> PasswordResetToken | None:
        """Get password reset token by code (for SMS)."""
        pass

    @abstractmethod
    def get_latest_by_code(self, code: str) -> PasswordResetToken | None:
        """Get latest password reset token by code (ordered by created_at desc)."""
        pass

    @abstractmethod
    def create(self, reset_token: PasswordResetToken) -> PasswordResetToken:
        """Create a new password reset token."""
        pass

    @abstractmethod
    def update(self, reset_token: PasswordResetToken) -> PasswordResetToken:
        """Update an existing password reset token."""
        pass

    @abstractmethod
    def invalidate_user_tokens(self, user_id: UUID, reset_type: str | None = None) -> int:
        """Invalidate all unused tokens for a user.

        Args:
            user_id: User ID
            reset_type: Reset type filter (optional)

        Returns:
            Number of tokens invalidated
        """
        pass
