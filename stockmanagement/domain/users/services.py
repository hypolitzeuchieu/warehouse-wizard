"""User domain services."""

from datetime import timedelta
from typing import Optional
from uuid import UUID, uuid4

from django.utils import timezone

from domain.users.entities import RefreshToken, Session
from domain.users.repositories import (
    DeviceRepository,
    RefreshTokenRepository,
    SessionRepository,
    UserRepository,
)


class UserDomainService:
    """User domain service."""

    def __init__(
        self,
        user_repository: UserRepository,
        session_repository: SessionRepository,
        refresh_token_repository: RefreshTokenRepository,
        device_repository: DeviceRepository,
    ) -> None:
        """Initialize user domain service."""
        self.user_repository = user_repository
        self.session_repository = session_repository
        self.refresh_token_repository = refresh_token_repository
        self.device_repository = device_repository

    def start_session(
        self,
        user_id: UUID,
        device_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Session:
        """Start a new user session."""
        session = Session(
            id=uuid4(),
            user_id=user_id,
            device_id=device_id,
            start_time=timezone.now(),
            end_time=None,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return self.session_repository.create(session)

    def end_session(self, session_id: UUID) -> Optional[Session]:
        """End a user session."""
        session = self.session_repository.get_by_id(session_id)
        if session and session.is_active:
            session.end_time = timezone.now()
            return self.session_repository.update(session)
        return None

    def end_user_sessions(
        self, user_id: UUID, device_id: Optional[str] = None
    ) -> None:
        """End all active sessions for a user (optionally for a specific device)."""
        active_sessions = self.session_repository.get_active_sessions_by_user(
            user_id
        )
        for session in active_sessions:
            if device_id is None or session.device_id == device_id:
                self.end_session(session.id)

    def create_refresh_token(
        self,
        user_id: UUID,
        token: str,
        device_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        expires_in_days: int = 30,
    ) -> RefreshToken:
        """Create a new refresh token."""
        refresh_token = RefreshToken(
            id=uuid4(),
            user_id=user_id,
            token=token,
            device_id=device_id,
            ip_address=ip_address,
            expires_at=timezone.now() + timedelta(days=expires_in_days),
            revoked=False,
            revoked_at=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return self.refresh_token_repository.create(refresh_token)

    def revoke_refresh_token(self, token_id: UUID) -> None:
        """Revoke a refresh token."""
        self.refresh_token_repository.revoke(token_id)

    def revoke_all_user_tokens(self, user_id: UUID) -> None:
        """Revoke all refresh tokens for a user."""
        self.refresh_token_repository.revoke_all_user_tokens(user_id)

    def revoke_user_device_tokens(
        self, user_id: UUID, device_id: str
    ) -> None:
        """Revoke refresh tokens for a specific user device."""
        self.refresh_token_repository.revoke_user_device_tokens(
            user_id, device_id
        )

