"""User domain services."""

import logging
from datetime import timedelta
from uuid import UUID, uuid4

from django.utils import timezone

from domain.business.repositories import BusinessMemberRepository, BusinessRepository
from domain.users.entities import RefreshToken, Session, User
from domain.users.repositories import (
    DeviceRepository,
    RefreshTokenRepository,
    SessionRepository,
    UserRepository,
)
from shared.exceptions.base import BaseAPIException

logger = logging.getLogger(__name__)


class UserDomainService:
    """User domain service."""

    def __init__(
        self,
        user_repository: UserRepository,
        session_repository: SessionRepository,
        refresh_token_repository: RefreshTokenRepository,
        device_repository: DeviceRepository,
        business_repository: BusinessRepository | None = None,
        business_member_repository: BusinessMemberRepository | None = None,
    ) -> None:
        """Initialize user domain service."""
        self.user_repository = user_repository
        self.session_repository = session_repository
        self.refresh_token_repository = refresh_token_repository
        self.device_repository = device_repository
        self.business_repository = business_repository
        self.business_member_repository = business_member_repository

    def start_session(
        self,
        user_id: UUID,
        device_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
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

    def end_session(self, session_id: UUID) -> Session | None:
        """End a user session."""
        session = self.session_repository.get_by_id(session_id)
        if session and session.is_active:
            session.end_time = timezone.now()
            return self.session_repository.update(session)
        return None

    def end_user_sessions(self, user_id: UUID, device_id: str | None = None) -> None:
        """End all active sessions for a user (optionally for a specific device)."""
        active_sessions = self.session_repository.get_active_sessions_by_user(user_id)
        for session in active_sessions:
            if device_id is None or session.device_id == device_id:
                self.end_session(session.id)

    def create_refresh_token(
        self,
        user_id: UUID,
        token: str,
        device_id: str | None = None,
        ip_address: str | None = None,
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

    def revoke_user_device_tokens(self, user_id: UUID, device_id: str) -> None:
        """Revoke refresh tokens for a specific user device."""
        self.refresh_token_repository.revoke_user_device_tokens(user_id, device_id)

    def validate_user_business_access(self, user: User) -> None:
        """
        Validate that user has active business access (for owners and members).

        This should be called only during login/OTP verification to ensure
        the user has valid business access before generating tokens.

        Args:
            user: User entity to validate

        Raises:
            BaseAPIException: If user doesn't have valid business access
        """

        if user.role.value not in ["owner", "customer", "wholesaler", "partner"]:
            if not self.business_member_repository or not self.business_repository:
                logger.warning(
                    f"Business repositories not injected for user {user.id}, "
                    f"skipping business access validation"
                )
                return

            memberships = self.business_member_repository.get_user_businesses(user.id)

            if not memberships:
                logger.warning(
                    f"Login attempt for member without business: {user.id}, role: {user.role.value}"
                )
                raise BaseAPIException(
                    detail="You are not associated with any business. Please contact support.",
                    code="NO_BUSINESS_ASSOCIATION",
                    status_code=403,
                )

            active_membership = next((m for m in memberships if m.is_active_member()), None)
            if not active_membership:
                logger.warning(f"Login attempt for inactive member: {user.id}")
                raise BaseAPIException(
                    detail="Your membership has been deactivated. Please contact your business owner.",
                    code="MEMBERSHIP_INACTIVE",
                    status_code=403,
                )

            business = self.business_repository.get_by_id(active_membership.business_id)
            if business and not business.is_active:
                logger.warning(
                    f"Login attempt for member of inactive business: {user.id}, business: {business.id}"
                )
                raise BaseAPIException(
                    detail="The business you belong to has been deactivated. Please contact support.",
                    code="BUSINESS_INACTIVE",
                    status_code=403,
                )

        if user.role.value == "owner":
            if not self.business_repository:
                logger.warning(
                    f"Business repository not injected for owner {user.id}, "
                    f"skipping business access validation"
                )
                return

            businesses = self.business_repository.get_by_owner(user.id)
            if businesses:
                active_business = next((b for b in businesses if b.is_active), None)
                if not active_business:
                    logger.warning(
                        f"Login attempt for owner with all businesses inactive: {user.id}"
                    )
                    raise BaseAPIException(
                        detail="All your businesses have been deactivated. Please contact support.",
                        code="BUSINESS_INACTIVE",
                        status_code=403,
                    )
