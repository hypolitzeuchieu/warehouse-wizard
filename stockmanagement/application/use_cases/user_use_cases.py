"""User use cases."""

from uuid import UUID, uuid4

from django.utils import timezone
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken

from application.dto.user_dto import (
    LoginDTO,
    LoginResponseDTO,
    LogoutDTO,
    RefreshTokenDTO,
    RefreshTokenResponseDTO,
    SessionResponseDTO,
    UserCreateDTO,
    UserResponseDTO,
)
from domain.users.entities import AuthMethod, Device, Session, User, UserRole
from domain.users.repositories import (
    DeviceRepository,
    RefreshTokenRepository,
    SessionRepository,
    UserRepository,
)
from domain.users.services import UserDomainService
from shared.exceptions.base import BaseAPIException
from shared.services.jwt_blacklist_service import JWTBlacklistService


class CreateUserUseCase:
    """Use case for creating a user."""

    def __init__(self, user_repository: UserRepository) -> None:
        """Initialize use case."""
        self.user_repository = user_repository

    def execute(self, dto: UserCreateDTO) -> UserResponseDTO:
        """Execute user creation."""
        if dto.email and self.user_repository.get_by_email(dto.email):
            raise BaseAPIException(
                detail="User with this email already exists",
                code="USER_ALREADY_EXISTS",
                status_code=400,
            )

        if dto.role == UserRole.MANAGER:
            raise BaseAPIException(
                detail="Users cannot signup with manager role",
                code="INVALID_ROLE",
                status_code=400,
            )

        name = dto.name
        if not name:
            name = dto.email.split("@")[0]

        # Create user entity
        user = User(
            id=uuid4(),
            email=dto.email,
            name=name,
            phone_number=dto.phone_number,
            role=dto.role,
            is_active=True,  # Account is active by default (can be disabled by admin)
            email_verified=False,  # Email/phone not verified yet
            is_staff=False,
            is_superuser=False,
            last_login=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            address=dto.address,
            avatar_url=None,
            auth_method=AuthMethod.EMAIL_PASSWORD,
        )

        user = self.user_repository.create(user, password=dto.password)
        return self._to_dto(user)

    def _to_dto(self, user: User) -> UserResponseDTO:
        """Convert user entity to DTO."""
        return UserResponseDTO(
            id=user.id,
            email=user.email or "",
            name=user.name,
            phone_number=user.phone_number,
            role=user.role.value if isinstance(user.role, UserRole) else user.role,
            is_active=user.is_active,
            email_verified=user.email_verified,
            is_staff=user.is_staff,
            is_superuser=user.is_superuser,
            last_login=user.last_login,
            address=user.address,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class LoginUseCase:
    """Use case for user login."""

    def __init__(
        self,
        user_repository: UserRepository,
        user_domain_service: UserDomainService,
        session_repository: SessionRepository,
        device_repository: DeviceRepository,
    ) -> None:
        """Initialize use case."""
        self.user_repository = user_repository
        self.user_domain_service = user_domain_service
        self.session_repository = session_repository
        self.device_repository = device_repository

    def execute(self, dto: LoginDTO, generate_tokens_func) -> LoginResponseDTO:
        """Execute login with email+password or phone+password."""
        # Find user by email or phone_number
        user_model = None
        if dto.email:
            user_model = self.user_repository.get_by_email(dto.email)
        elif dto.phone_number:
            user_model = self.user_repository.get_by_phone_number(dto.phone_number)

        if not user_model:
            raise BaseAPIException(
                detail="Invalid credentials",
                code="INVALID_CREDENTIALS",
                status_code=401,
            )

        # Verify password using repository
        if not self.user_repository.verify_password(user_model.id, dto.password):
            raise BaseAPIException(
                detail="Invalid credentials",
                code="INVALID_CREDENTIALS",
                status_code=401,
            )

        # Check if account is active (not disabled by admin)
        if not user_model.is_active:
            raise BaseAPIException(
                detail="Your account has been disabled. Please contact support.",
                code="ACCOUNT_DISABLED",
                status_code=403,
            )

        # Check if email is verified
        if not user_model.email_verified:
            raise BaseAPIException(
                detail="Please verify your email/phone with OTP first.",
                code="EMAIL_NOT_VERIFIED",
                status_code=403,
            )

        # Start session
        self.user_domain_service.start_session(
            user_id=user_model.id,
            device_id=dto.device_id,
            ip_address=dto.ip_address,
            user_agent=dto.user_agent,
        )

        # Register or update device
        if dto.device_id:
            device = self.device_repository.get_by_device_id(dto.device_id)
            if device:
                device.last_used_at = timezone.now()
                self.device_repository.update(device)
            else:
                device = Device(
                    id=uuid4(),
                    user_id=user_model.id,
                    device_id=dto.device_id,
                    device_name=dto.device_name,
                    device_type=dto.device_type,
                    ip_address=dto.ip_address,
                    user_agent=dto.user_agent,
                    last_used_at=timezone.now(),
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                )
                self.device_repository.create(device)

        # Generate tokens
        tokens = generate_tokens_func(user_model)

        # Create refresh token
        self.user_domain_service.create_refresh_token(
            user_id=user_model.id,
            token=tokens["refresh"],
            device_id=dto.device_id,
            ip_address=dto.ip_address,
        )

        return LoginResponseDTO(
            access_token=tokens["access"],
            refresh_token=tokens["refresh"],
            user=UserResponseDTO(
                id=user_model.id,
                email=user_model.email or "",
                name=user_model.name,
                phone_number=user_model.phone_number,
                role=(
                    user_model.role.value
                    if isinstance(user_model.role, UserRole)
                    else user_model.role
                ),
                is_active=user_model.is_active,
                email_verified=user_model.email_verified,
                is_staff=user_model.is_staff,
                is_superuser=user_model.is_superuser,
                last_login=timezone.now(),
                address=user_model.address,
                avatar_url=user_model.avatar_url,
                created_at=user_model.created_at,
                updated_at=user_model.updated_at,
            ),
            expires_in=3600,  # 1 hour
        )


class RefreshTokenUseCase:
    """Use case for refreshing access token."""

    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        user_repository: UserRepository,
        user_domain_service: UserDomainService,
    ) -> None:
        """Initialize use case."""
        self.refresh_token_repository = refresh_token_repository
        self.user_repository = user_repository
        self.user_domain_service = user_domain_service

    def execute(self, dto: RefreshTokenDTO, generate_tokens_func) -> RefreshTokenResponseDTO:
        """Execute token refresh."""
        # First, validate JWT token expiration and blacklist
        # JWTRefreshToken automatically validates expiration (exp claim)
        # If expired, it will raise InvalidToken
        try:
            refresh_token_jwt = JWTRefreshToken(dto.refresh_token)

            jti = refresh_token_jwt.get("jti")

            if jti:
                if JWTBlacklistService.is_token_blacklisted(jti):
                    raise BaseAPIException(
                        detail="Refresh token has been blacklisted (logged out)",
                        code="REFRESH_TOKEN_BLACKLISTED",
                        status_code=401,
                    )
        except InvalidToken as e:
            # Invalid JWT token format or expired
            # JWTRefreshToken automatically checks expiration (exp claim)
            raise BaseAPIException(
                detail=f"Invalid or expired refresh token: {str(e)}",
                code="INVALID_REFRESH_TOKEN",
                status_code=401,
            ) from e
        except Exception as e:
            # Log error but continue with repository check
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Error checking refresh token blacklist: {e}", exc_info=True)

        # Get refresh token from repository
        refresh_token = self.refresh_token_repository.get_by_token(dto.refresh_token)

        if not refresh_token or not refresh_token.is_valid():
            raise BaseAPIException(
                detail="Invalid or expired refresh token",
                code="INVALID_REFRESH_TOKEN",
                status_code=401,
            )

        # Get user
        user = self.user_repository.get_by_id(refresh_token.user_id)
        if not user or not user.is_active:
            raise BaseAPIException(
                detail="User not found or inactive",
                code="USER_NOT_FOUND",
                status_code=404,
            )

        # Blacklist and revoke old refresh token AND its associated access token
        # This ensures that when a refresh token is used, both the refresh token
        # and its associated access token become invalid immediately
        try:
            JWTBlacklistService.blacklist_tokens_from_refresh_token(
                refresh_token_string=dto.refresh_token,
                user_id=refresh_token.user_id,
            )
        except Exception as e:
            # Log error but continue with revocation
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to blacklist old refresh/access tokens: {e}", exc_info=True)

        # Revoke old refresh token in our database
        self.user_domain_service.revoke_refresh_token(refresh_token.id)

        # Generate new tokens
        tokens = generate_tokens_func(user)

        # Create new refresh token (rotation)
        self.user_domain_service.create_refresh_token(
            user_id=user.id,
            token=tokens["refresh"],
            device_id=dto.device_id or refresh_token.device_id,
            ip_address=refresh_token.ip_address,
        )

        return RefreshTokenResponseDTO(
            access_token=tokens["access"],
            refresh_token=tokens["refresh"],
            expires_in=3600,  # 1 hour
        )


class LogoutUseCase:
    """Use case for user logout."""

    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        session_repository: SessionRepository,
        user_domain_service: UserDomainService,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.refresh_token_repository = refresh_token_repository
        self.session_repository = session_repository
        self.user_domain_service = user_domain_service
        self.user_id = user_id

    def execute(self, dto: LogoutDTO) -> None:
        """Execute logout."""
        # End active sessions
        if dto.logout_all_devices:
            self.user_domain_service.end_user_sessions(self.user_id)
            self.user_domain_service.revoke_all_user_tokens(self.user_id)
        elif dto.device_id:
            self.user_domain_service.end_user_sessions(self.user_id, dto.device_id)
            self.user_domain_service.revoke_user_device_tokens(self.user_id, dto.device_id)
        else:
            # End current session (would need to track current session)
            active_sessions = self.session_repository.get_active_sessions_by_user(self.user_id)
            for session in active_sessions:
                self.user_domain_service.end_session(session.id)


class GetUserSessionsUseCase:
    """Use case for getting user sessions."""

    def __init__(self, session_repository: SessionRepository, user_id: UUID) -> None:
        """Initialize use case."""
        self.session_repository = session_repository
        self.user_id = user_id

    def execute(self, limit: int = 100, offset: int = 0) -> list[SessionResponseDTO]:
        """Execute getting sessions."""
        # Use the new method that includes device information
        if hasattr(self.session_repository, "get_user_sessions_with_devices"):
            sessions_with_devices = self.session_repository.get_user_sessions_with_devices(
                self.user_id, limit, offset
            )
            return [
                self._to_dto_with_device(session, device)
                for session, device in sessions_with_devices
            ]
        else:
            # Fallback to old method if not available
            sessions = self.session_repository.get_user_sessions(self.user_id, limit, offset)
            return [self._to_dto(session) for session in sessions]

    def _to_dto(self, session: Session) -> SessionResponseDTO:
        """Convert session entity to DTO."""
        return SessionResponseDTO(
            id=session.id,
            user_id=session.user_id,
            device_id=session.device_id,
            start_time=session.start_time,
            end_time=session.end_time,
            duration_seconds=session.duration_seconds,
            is_active=session.is_active,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            created_at=session.created_at,
        )

    def _to_dto_with_device(self, session: Session, device: Device | None) -> SessionResponseDTO:
        """Convert session entity to DTO with device information."""
        return SessionResponseDTO(
            id=session.id,
            user_id=session.user_id,
            device_id=session.device_id,
            device_name=device.device_name if device else None,
            device_type=device.device_type if device else None,
            start_time=session.start_time,
            end_time=session.end_time,
            duration_seconds=session.duration_seconds,
            is_active=session.is_active,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            created_at=session.created_at,
        )
