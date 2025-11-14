import logging
from uuid import UUID, uuid4

from django.utils import timezone
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken

from application.dto.user_dto import (
    LoginDTO,
    LoginResponseDTO,
    LogoutDTO,
    OTPRequestDTO,
    RefreshTokenDTO,
    RefreshTokenResponseDTO,
    SessionResponseDTO,
    SignupResponseDTO,
    UserCreateDTO,
    UserResponseDTO,
)
from domain.users.entities import AuthMethod, Device, Session, User, UserRole
from domain.users.repositories import (
    DeviceRepository,
    OTPRepository,
    RefreshTokenRepository,
    SessionRepository,
    UserRepository,
)
from domain.users.services import UserDomainService
from shared.authentication.jwt_blacklist_service import JWTBlacklistService
from shared.exceptions.base import BaseAPIException

logger = logging.getLogger(__name__)


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
            if dto.email:
                name = dto.email.split("@")[0]
            elif dto.phone_number:
                name = f"user_{dto.phone_number[-4:]}"
            else:
                name = "user"

        # Create user entity
        user = User(
            id=uuid4(),
            email=dto.email,
            name=name,
            phone_number=dto.phone_number,
            role=dto.role,
            is_active=True,
            email_verified=False,
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


class SignupUseCase:
    """Use case for user signup with automatic OTP sending."""

    def __init__(
        self,
        user_repository: UserRepository,
        otp_repository: OTPRepository,
    ) -> None:
        """Initialize use case."""
        self.user_repository = user_repository
        self.otp_repository = otp_repository

        from application.use_cases.otp_use_cases import RequestOTPUseCase

        self.otp_use_case = RequestOTPUseCase(
            otp_repository=otp_repository,
            user_repository=user_repository,
        )

    def execute(self, dto: UserCreateDTO) -> SignupResponseDTO:
        """
        Execute user signup with automatic OTP sending.

        Priority: Email OTP if email is provided, otherwise SMS OTP.

        Args:
            dto: User creation DTO

        Returns:
            SignupResponseDTO with OTP delivery information

        Raises:
            BaseAPIException: If user creation fails or OTP sending fails
        """

        # Create user
        create_user_use_case = CreateUserUseCase(user_repository=self.user_repository)
        user_dto = create_user_use_case.execute(dto)

        logger.info(
            f"User created successfully - ID: {user_dto.id}, "
            f"email: {user_dto.email}, phone: {user_dto.phone_number}"
        )

        otp_type = None
        otp_destination = None
        otp_sent = False
        expires_in_minutes = None
        if user_dto.email:
            otp_type = "email"
            otp_destination = user_dto.email
            try:
                logger.debug(f"Sending OTP to email: {user_dto.email}")
                otp_request_dto = OTPRequestDTO(
                    email=user_dto.email,
                )
                result = self.otp_use_case.execute(otp_request_dto)
                otp_sent = True
                expires_in_minutes = result.get("expires_in_minutes", 10)
                logger.info(
                    f"OTP sent successfully to {user_dto.email} - "
                    f"expires in {expires_in_minutes} minutes"
                )
            except Exception as otp_error:
                logger.error(
                    f"Failed to send OTP on signup for user {user_dto.id} "
                    f"({user_dto.email}): {str(otp_error)}",
                    exc_info=True,
                    extra={"user_id": str(user_dto.id), "email": user_dto.email},
                )
        elif user_dto.phone_number:
            otp_type = "sms"
            otp_destination = user_dto.phone_number
            try:
                logger.debug(f"Sending OTP to phone: {user_dto.phone_number}")
                otp_request_dto = OTPRequestDTO(
                    phone_number=user_dto.phone_number,
                )
                result = self.otp_use_case.execute(otp_request_dto)
                otp_sent = True
                expires_in_minutes = result.get("expires_in_minutes", 10)
                logger.info(
                    f"OTP sent successfully to {user_dto.phone_number} - "
                    f"expires in {expires_in_minutes} minutes"
                )
            except Exception as otp_error:
                logger.error(
                    f"Failed to send OTP on signup for user {user_dto.id} "
                    f"({user_dto.phone_number}): {str(otp_error)}",
                    exc_info=True,
                    extra={
                        "user_id": str(user_dto.id),
                        "phone_number": user_dto.phone_number,
                    },
                )

        if otp_sent:
            if otp_type == "email":
                destination_description = f"your email ({otp_destination})"
                check_instruction = "Please check your inbox and verify your account."
            else:  # SMS
                destination_description = f"your phone number ({otp_destination})"
                check_instruction = "Please check your messages and verify your account."
            message = (
                f"Account created successfully. "
                f"An OTP has been sent to {destination_description}. "
                f"{check_instruction} "
                f"The OTP will expire in {expires_in_minutes} minutes."
            )
        else:
            # Fallback if OTP sending failed
            message = (
                "Account created successfully, but we encountered an issue "
                "sending the OTP. Please request a new OTP using the "
                "request OTP endpoint."
            )

        return SignupResponseDTO(
            message=message,
            expires_in_minutes=expires_in_minutes or 0,
            email=user_dto.email if otp_type == "email" else None,
            phone_number=user_dto.phone_number if otp_type == "sms" else None,
            otp_type=otp_type,
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

        if not self.user_repository.verify_password(user_model.id, dto.password):
            raise BaseAPIException(
                detail="Invalid credentials",
                code="INVALID_CREDENTIALS",
                status_code=401,
            )

        if not user_model.is_active:
            raise BaseAPIException(
                detail="Your account has been disabled. Please contact support.",
                code="ACCOUNT_DISABLED",
                status_code=403,
            )

        if not user_model.email_verified:
            raise BaseAPIException(
                detail="Please verify your email/phone with OTP first.",
                code="EMAIL_NOT_VERIFIED",
                status_code=403,
            )

        self.user_domain_service.start_session(
            user_id=user_model.id,
            device_id=dto.device_id,
            ip_address=dto.ip_address,
            user_agent=dto.user_agent,
        )

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

        tokens = generate_tokens_func(user_model)

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
            raise BaseAPIException(
                detail=f"Invalid or expired refresh token: {str(e)}",
                code="INVALID_REFRESH_TOKEN",
                status_code=401,
            ) from e
        except Exception as e:
            logger.warning(f"Error checking refresh token blacklist: {e}", exc_info=True)

        refresh_token = self.refresh_token_repository.get_by_token(dto.refresh_token)

        if not refresh_token or not refresh_token.is_valid():
            raise BaseAPIException(
                detail="Invalid or expired refresh token",
                code="INVALID_REFRESH_TOKEN",
                status_code=401,
            )

        user = self.user_repository.get_by_id(refresh_token.user_id)
        if not user or not user.is_active:
            raise BaseAPIException(
                detail="User not found or inactive",
                code="USER_NOT_FOUND",
                status_code=404,
            )

        try:
            JWTBlacklistService.blacklist_tokens_from_refresh_token(
                refresh_token_string=dto.refresh_token,
                user_id=refresh_token.user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to blacklist old refresh/access tokens: {e}", exc_info=True)

        self.user_domain_service.revoke_refresh_token(refresh_token.id)

        tokens = generate_tokens_func(user)

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
        if dto.logout_all_devices:
            self.user_domain_service.end_user_sessions(self.user_id)
            self.user_domain_service.revoke_all_user_tokens(self.user_id)
        elif dto.device_id:
            self.user_domain_service.end_user_sessions(self.user_id, dto.device_id)
            self.user_domain_service.revoke_user_device_tokens(self.user_id, dto.device_id)
        else:
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
        if hasattr(self.session_repository, "get_user_sessions_with_devices"):
            sessions_with_devices = self.session_repository.get_user_sessions_with_devices(
                self.user_id, limit, offset
            )
            return [
                self._to_dto_with_device(session, device)
                for session, device in sessions_with_devices
            ]
        else:
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
