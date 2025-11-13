from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from application.dto.user_dto import OTPRequestDTO
from application.use_cases.google_oauth_use_case import (
    GoogleOAuthAuthURLUseCase,
    GoogleOAuthCodeUseCase,
)
from application.use_cases.otp_use_cases import RequestOTPUseCase, VerifyOTPUseCase
from application.use_cases.password_reset_use_cases import (
    ForgotPasswordUseCase,
    ResetPasswordUseCase,
)
from application.use_cases.profile_use_cases import GetProfileUseCase, UpdateProfileUseCase
from application.use_cases.user_use_cases import (
    CreateUserUseCase,
    GetUserSessionsUseCase,
    LogoutUseCase,
    RefreshTokenUseCase,
)
from domain.users.services import UserDomainService
from infrastructure.external.google_oauth import GoogleOAuthService
from infrastructure.persistence.repositories import (
    DeviceRepositoryImpl,
    OTPRepositoryImpl,
    RefreshTokenRepositoryImpl,
    SessionRepositoryImpl,
    UserRepositoryImpl,
)
from presentation.serializers.user_serializers import (
    ForgotPasswordSerializer,
    GoogleOAuthCodeSerializer,
    LoginSerializer,
    LogoutSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    ProfileUpdateSerializer,
    RefreshTokenSerializer,
    ResetPasswordSerializer,
    UserCreateSerializer,
)
from shared.rate_limiting.decorators import rate_limit
from shared.utils.jwt import generate_tokens
from shared.views.functional_view_helper import FunctionalViewHelper

logger = logging.getLogger(__name__)


@swagger_auto_schema(
    method="post",
    operation_summary="User Signup",
    operation_description="Create a new user account. OTP will be sent automatically to verify the account.",
    request_body=UserCreateSerializer,
    responses={
        201: "User created successfully",
        400: "Bad Request",
        500: "Internal Server Error",
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@rate_limit(requests_per_period=5, period_seconds=3600)
def signup_view(request: Request) -> Response:
    """User signup endpoint."""
    helper = FunctionalViewHelper(request)
    serializer = UserCreateSerializer(data=request.data)

    logger.info(
        f"Signup attempt - email: {request.data.get('email', 'N/A')}, "
        f"phone: {request.data.get('phone_number', 'N/A')}"
    )

    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your input.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        logger.warning(
            f"Signup validation failed - email: {request.data.get('email', 'N/A')}",
            extra={"errors": serializer.errors},
        )
        return validation_error

    try:
        dto = serializer.to_dto()
        logger.debug(f"Creating user with email: {dto.email}, role: {dto.role}")
        use_case = CreateUserUseCase(user_repository=UserRepositoryImpl())
        user_dto = use_case.execute(dto)
        logger.info(f"User created successfully - ID: {user_dto.id}, email: {user_dto.email}")

        # Send OTP automatically on signup
        otp_sent = False
        expires_in_minutes = None
        otp_type = None
        otp_destination = None

        otp_use_case = RequestOTPUseCase(
            otp_repository=OTPRepositoryImpl(),
            user_repository=UserRepositoryImpl(),
        )

        if user_dto.email:
            # Send OTP via email
            try:
                logger.debug(f"Sending OTP to email: {user_dto.email}")
                otp_request_dto = OTPRequestDTO(
                    email=user_dto.email,
                    otp_type="email",
                )
                otp_result = otp_use_case.execute(otp_request_dto)
                otp_sent = True
                otp_type = "email"
                otp_destination = user_dto.email
                expires_in_minutes = otp_result.get("expires_in_minutes", 10)
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
            # Send OTP via SMS if email is not provided
            try:
                logger.debug(f"Sending OTP to phone: {user_dto.phone_number}")
                otp_request_dto = OTPRequestDTO(
                    phone_number=user_dto.phone_number,
                    otp_type="sms",
                )
                otp_result = otp_use_case.execute(otp_request_dto)
                otp_sent = True
                otp_type = "sms"
                otp_destination = user_dto.phone_number
                expires_in_minutes = otp_result.get("expires_in_minutes", 10)
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

        # Return success message indicating OTP was sent
        if otp_sent:
            if otp_type == "email":
                message = (
                    f"Account created successfully. "
                    f"An OTP has been sent to your email ({otp_destination}). "
                    f"Please check your inbox and verify your account. "
                    f"The OTP will expire in {expires_in_minutes} minutes."
                )
                data = {
                    "expires_in_minutes": expires_in_minutes,
                    "email": otp_destination,
                }
            else:  # SMS
                message = (
                    f"Account created successfully. "
                    f"An OTP has been sent to your phone number ({otp_destination}). "
                    f"Please check your messages and verify your account. "
                    f"The OTP will expire in {expires_in_minutes} minutes."
                )
                data = {
                    "expires_in_minutes": expires_in_minutes,
                    "phone_number": otp_destination,
                }

            return helper.success(
                message=message,
                data=data,
                status_code=status.HTTP_201_CREATED,
            )
        else:
            # Fallback if OTP sending failed
            message = (
                "Account created successfully, but we encountered an issue "
                "sending the OTP. Please request a new OTP using the "
                "request OTP endpoint."
            )
            fallback_data = {}
            if user_dto.email:
                fallback_data["email"] = user_dto.email
            if user_dto.phone_number:
                fallback_data["phone_number"] = user_dto.phone_number

            return helper.success(
                message=message,
                data=fallback_data,
                status_code=status.HTTP_201_CREATED,
            )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="post",
    operation_summary="User Login",
    request_body=LoginSerializer,
    responses={
        200: "Credentials verified, OTP sent successfully",
        400: "Invalid credentials or validation error",
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@rate_limit(requests_per_period=10, period_seconds=900)
def login_view(request: Request) -> Response:
    """User login endpoint - verifies credentials and sends OTP."""
    helper = FunctionalViewHelper(request)
    serializer = LoginSerializer(data=request.data)

    # Check validation
    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your credentials.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        dto = serializer.to_dto(request)
        identifier = dto.email or dto.phone_number or "unknown"
        logger.info(f"Login attempt - identifier: {identifier}")

        # Find user by email or phone_number
        user = None
        if dto.email:
            user = UserRepositoryImpl().get_by_email(dto.email)
            logger.debug(f"User lookup by email: {dto.email} - found: {user is not None}")
        elif dto.phone_number:
            user = UserRepositoryImpl().get_by_phone_number(dto.phone_number)
            logger.debug(f"User lookup by phone: {dto.phone_number} - found: {user is not None}")

        if not user:
            logger.warning(f"Login failed - user not found: {identifier}")
            return helper.error(
                message="Invalid credentials",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_CREDENTIALS",
            )

        # Verify password using repository
        user_repository = UserRepositoryImpl()
        if not user_repository.verify_password(user.id, dto.password):
            logger.warning(f"Login failed - invalid password for user: {user.id} ({identifier})")
            return helper.error(
                message="Invalid credentials",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_CREDENTIALS",
            )

        # Check if account is active (not disabled by admin)
        if not user.is_active:
            logger.warning(f"Login failed - account disabled: {user.id} ({identifier})")
            return helper.error(
                message="Your account has been disabled. Please contact support.",
                status_code=status.HTTP_403_FORBIDDEN,
                code="ACCOUNT_DISABLED",
            )

        # Credentials are valid - send OTP even if email is not verified
        # Email will be verified automatically when OTP is verified
        if not user.email_verified:
            logger.info(
                f"Login with unverified email - sending OTP to verify: {user.id} ({identifier})"
            )
        else:
            logger.debug(f"Credentials verified for user: {user.id} ({identifier})")

        # Credentials are valid, send OTP
        otp_use_case = RequestOTPUseCase(
            otp_repository=OTPRepositoryImpl(),
            user_repository=UserRepositoryImpl(),
        )

        # Determine OTP type based on the identifier used for login
        # If user logged in with email, send OTP via email
        # If user logged in with phone, send OTP via SMS
        if dto.email:
            # User logged in with email, send OTP via email
            otp_type = "email"
            otp_request_dto = OTPRequestDTO(
                email=user.email,
                otp_type=otp_type,
            )
        elif dto.phone_number:
            # User logged in with phone, send OTP via SMS
            otp_type = "sms"
            otp_request_dto = OTPRequestDTO(
                phone_number=user.phone_number,
                otp_type=otp_type,
            )
        else:
            # Fallback: use email if available, otherwise SMS
            otp_type = "email" if user.email else "sms"
            otp_request_dto = OTPRequestDTO(
                email=user.email if user.email else None,
                phone_number=user.phone_number if not user.email else None,
                otp_type=otp_type,
            )

        result = otp_use_case.execute(otp_request_dto)
        logger.info(
            f"OTP sent for login - user: {user.id} ({identifier}), "
            f"type: {otp_type}, expires in: {result.get('expires_in_minutes')} minutes"
        )

        return helper.success(
            message="Credentials verified. OTP sent successfully. Please verify OTP to complete login.",
            data={
                "expires_in_minutes": result["expires_in_minutes"],
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="post",
    operation_summary="Verify OTP",
    operation_description="Verify OTP code and receive access/refresh tokens.",
    request_body=OTPVerifySerializer,
    responses={200: "OTP verified successfully.", 400: "Invalid or expired OTP."},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@rate_limit(requests_per_period=5, period_seconds=300)
def verify_otp_view(request: Request) -> Response:
    """OTP verification endpoint - returns tokens after verification."""
    helper = FunctionalViewHelper(request)
    serializer = OTPVerifySerializer(data=request.data)

    # Check validation
    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your OTP code.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        dto = serializer.to_dto()

        # Get device info from request
        from shared.rate_limiting.decorators import get_client_ip
        from shared.utils.device import get_or_detect_device_type

        device_id = serializer.validated_data.get("device_id")
        device_name = serializer.validated_data.get("device_name")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        provided_device_type = serializer.validated_data.get("device_type")
        device_type = get_or_detect_device_type(provided_device_type, user_agent)
        ip_address = get_client_ip(request)

        user_domain_service = UserDomainService(
            user_repository=UserRepositoryImpl(),
            session_repository=SessionRepositoryImpl(),
            refresh_token_repository=RefreshTokenRepositoryImpl(),
            device_repository=DeviceRepositoryImpl(),
        )

        use_case = VerifyOTPUseCase(
            otp_repository=OTPRepositoryImpl(),
            user_repository=UserRepositoryImpl(),
            user_domain_service=user_domain_service,
            session_repository=SessionRepositoryImpl(),
            device_repository=DeviceRepositoryImpl(),
        )

        def generate_tokens_func(user: Any) -> dict[str, Any]:
            """Generate JWT tokens."""
            return generate_tokens(user)

        login_response = use_case.execute(
            dto,
            generate_tokens_func,
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        from presentation.serializers.user_serializers import UserResponseSerializer

        return helper.success(
            message="OTP verified successfully. Login completed.",
            data={
                "access_token": login_response.access_token,
                "refresh_token": login_response.refresh_token,
                "expires_in": login_response.expires_in,
                "user": UserResponseSerializer.from_dto(login_response.user),
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="post",
    operation_summary="Request OTP",
    operation_description="Request an OTP code via email or SMS.",
    request_body=OTPRequestSerializer,
    responses={
        200: openapi.Response(description="OTP sent successfully"),
        400: openapi.Response(description="Validation error"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@rate_limit(requests_per_period=3, period_seconds=300)
def request_otp_view(request: Request) -> Response:
    """Request OTP endpoint."""
    helper = FunctionalViewHelper(request)
    serializer = OTPRequestSerializer(data=request.data)

    # Check validation
    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your OTP request.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        dto = serializer.to_dto()
        use_case = RequestOTPUseCase(
            otp_repository=OTPRepositoryImpl(),
            user_repository=UserRepositoryImpl(),
        )
        result = use_case.execute(dto)

        return helper.success(
            message=result["message"],
            data={
                "expires_in_minutes": result["expires_in_minutes"],
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="get",
    operation_summary="Get Google OAuth URL",
    operation_description="Generate Google OAuth authorization URL.",
    responses={
        200: openapi.Response(description="Auth URL generated successfully"),
        503: openapi.Response(description="Google OAuth not configured"),
    },
    tags=["Authentication"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
@rate_limit(requests_per_period=10, period_seconds=60)
def google_auth_url_view(request: Request) -> Response:
    """Generate Google OAuth authorization URL endpoint."""
    helper = FunctionalViewHelper(request)

    try:
        if not GoogleOAuthService.is_configured():
            return helper.error(
                message="Google OAuth is not configured",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="SERVICE_UNAVAILABLE",
            )

        use_case = GoogleOAuthAuthURLUseCase(google_oauth_service=GoogleOAuthService())
        response_dto = use_case.execute()

        return helper.success(
            message="Google OAuth authorization URL generated successfully",
            data={
                "auth_url": response_dto.auth_url,
            },
            status_code=status.HTTP_200_OK,
        )
    except ValueError as e:
        return helper.error(
            message=str(e),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SERVICE_UNAVAILABLE",
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="post",
    operation_summary="Google OAuth Callback",
    operation_description="Exchange Google OAuth code for access token and authenticate user.",
    request_body=GoogleOAuthCodeSerializer,
    responses={
        200: openapi.Response(description="Google OAuth authentication successful"),
        400: openapi.Response(description="Validation error"),
        401: openapi.Response(description="Invalid Google OAuth code"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@rate_limit(requests_per_period=5, period_seconds=300)
def google_callback_view(request: Request) -> Response:
    """Google OAuth callback endpoint - exchanges code for tokens."""
    helper = FunctionalViewHelper(request)
    serializer = GoogleOAuthCodeSerializer(data=request.data)

    # Check validation
    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your Google OAuth code.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        if not GoogleOAuthService.is_configured():
            return helper.error(
                message="Google OAuth is not configured",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="SERVICE_UNAVAILABLE",
            )

        dto = serializer.to_dto(request)
        user_domain_service = UserDomainService(
            user_repository=UserRepositoryImpl(),
            session_repository=SessionRepositoryImpl(),
            refresh_token_repository=RefreshTokenRepositoryImpl(),
            device_repository=DeviceRepositoryImpl(),
        )
        use_case = GoogleOAuthCodeUseCase(
            user_repository=UserRepositoryImpl(),
            user_domain_service=user_domain_service,
            session_repository=SessionRepositoryImpl(),
            device_repository=DeviceRepositoryImpl(),
            google_oauth_service=GoogleOAuthService(),
        )

        login_response = use_case.execute(dto, generate_tokens)

        from presentation.serializers.user_serializers import UserResponseSerializer

        return helper.success(
            message="Google OAuth authentication successful",
            data={
                "access_token": login_response.access_token,
                "refresh_token": login_response.refresh_token,
                "expires_in": login_response.expires_in,
                "user": UserResponseSerializer.from_dto(login_response.user),
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="post",
    operation_summary="Refresh Token",
    operation_description="Refresh access token using refresh token.",
    request_body=RefreshTokenSerializer,
    responses={
        200: openapi.Response(description="Token refreshed successfully"),
        400: openapi.Response(description="Invalid refresh token"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_token_view(request: Request) -> Response:
    """Refresh token endpoint."""
    helper = FunctionalViewHelper(request)
    serializer = RefreshTokenSerializer(data=request.data)

    # Check validation
    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your refresh token.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        dto = serializer.to_dto()
        user_domain_service = UserDomainService(
            user_repository=UserRepositoryImpl(),
            session_repository=SessionRepositoryImpl(),
            refresh_token_repository=RefreshTokenRepositoryImpl(),
            device_repository=DeviceRepositoryImpl(),
        )
        use_case = RefreshTokenUseCase(
            refresh_token_repository=RefreshTokenRepositoryImpl(),
            user_repository=UserRepositoryImpl(),
            user_domain_service=user_domain_service,
        )

        def generate_tokens_func(user: Any) -> dict[str, Any]:
            """Generate JWT tokens."""
            return generate_tokens(user)

        refresh_response = use_case.execute(dto, generate_tokens_func)

        return helper.success(
            message="Token refreshed successfully",
            data={
                "access_token": refresh_response.access_token,
                "refresh_token": refresh_response.refresh_token,
                "expires_in": refresh_response.expires_in,
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="post",
    operation_summary="Logout",
    operation_description="Logout user from current device or all devices. Use logout_all_devices=true to logout from all devices, or provide device_id to logout from a specific device.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "device_id": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Optional: Device ID to logout from a specific device",
                example="device-123",
            ),
            "logout_all_devices": openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description="Set to true to logout from all devices",
                default=False,
                example=True,
            ),
        },
        required=[],
    ),
    responses={
        200: openapi.Response(description="Logout successful"),
        400: openapi.Response(description="Validation error"),
        401: openapi.Response(description="Unauthorized"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request: Request) -> Response:
    """User logout endpoint."""
    helper = FunctionalViewHelper(request)
    serializer = LogoutSerializer(data=request.data)

    # Check validation
    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your logout request.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token_string = auth_header.split(" ")[1]
            try:
                # Decode the token to get jti and expiration
                access_token = AccessToken(token_string)
                jti = access_token.get("jti")

                # Blacklist the access token
                if jti:
                    try:
                        # Try to find existing OutstandingToken by jti
                        outstanding_token = OutstandingToken.objects.get(jti=jti)
                    except OutstandingToken.DoesNotExist:
                        # Create OutstandingToken for this access token
                        exp_timestamp = access_token.get("exp")
                        iat_timestamp = access_token.get("iat")
                        expires_at = (
                            datetime.fromtimestamp(exp_timestamp, tz=UTC)
                            if exp_timestamp
                            else timezone.now() + timezone.timedelta(hours=1)
                        )
                        created_at = (
                            datetime.fromtimestamp(iat_timestamp, tz=UTC)
                            if iat_timestamp
                            else timezone.now()
                        )

                        outstanding_token = OutstandingToken.objects.create(
                            jti=jti,
                            user=request.user,
                            token=token_string,
                            created_at=created_at,
                            expires_at=expires_at,
                        )
                        logger.info(f"Created OutstandingToken for access token (jti: {jti})")

                    # Blacklist the token (this will prevent it from being used)
                    BlacklistedToken.objects.get_or_create(token=outstanding_token)
                    logger.info(f"Access token blacklisted for user {request.user.id} (jti: {jti})")
            except Exception as token_error:
                logger.warning(
                    f"Failed to blacklist access token: {str(token_error)}. "
                    f"Continuing with logout anyway.",
                    exc_info=True,
                )

        dto = serializer.to_dto()
        user_domain_service = UserDomainService(
            user_repository=UserRepositoryImpl(),
            session_repository=SessionRepositoryImpl(),
            refresh_token_repository=RefreshTokenRepositoryImpl(),
            device_repository=DeviceRepositoryImpl(),
        )

        # Get refresh tokens to blacklist before revoking them
        refresh_token_repo = RefreshTokenRepositoryImpl()
        if dto.logout_all_devices:
            # Get all active refresh tokens for this user
            refresh_tokens = refresh_token_repo.get_by_user_and_device(request.user.id, None)
        elif dto.device_id:
            # Get refresh tokens for specific device
            refresh_tokens = refresh_token_repo.get_by_user_and_device(
                request.user.id, dto.device_id
            )
        else:
            # Get all active refresh tokens (for current session logout)
            refresh_tokens = refresh_token_repo.get_by_user_and_device(request.user.id, None)

        # Blacklist all refresh tokens JWT in simplejwt blacklist system
        for refresh_token_entity in refresh_tokens:
            if refresh_token_entity.token and not refresh_token_entity.revoked:
                try:
                    # Decode the refresh token JWT to get jti
                    refresh_token_jwt = RefreshToken(refresh_token_entity.token)
                    jti = refresh_token_jwt.get("jti")

                    if jti:
                        try:
                            # Try to find existing OutstandingToken by jti
                            outstanding_token = OutstandingToken.objects.get(jti=jti)
                        except OutstandingToken.DoesNotExist:
                            # Create OutstandingToken for this refresh token
                            exp_timestamp = refresh_token_jwt.get("exp")
                            iat_timestamp = refresh_token_jwt.get("iat")
                            expires_at = (
                                datetime.fromtimestamp(exp_timestamp, tz=UTC)
                                if exp_timestamp
                                else timezone.now() + timezone.timedelta(days=30)
                            )
                            created_at = (
                                datetime.fromtimestamp(iat_timestamp, tz=UTC)
                                if iat_timestamp
                                else timezone.now()
                            )

                            outstanding_token = OutstandingToken.objects.create(
                                jti=jti,
                                user=request.user,
                                token=refresh_token_entity.token,
                                created_at=created_at,
                                expires_at=expires_at,
                            )
                            logger.info(f"Created OutstandingToken for refresh token (jti: {jti})")

                        # Blacklist the refresh token
                        BlacklistedToken.objects.get_or_create(token=outstanding_token)
                        logger.info(
                            f"Refresh token blacklisted for user {request.user.id} (jti: {jti})"
                        )
                except Exception as refresh_token_error:
                    logger.warning(
                        f"Failed to blacklist refresh token {refresh_token_entity.id}: {str(refresh_token_error)}. "
                        f"Continuing with logout anyway.",
                        exc_info=True,
                    )

        use_case = LogoutUseCase(
            refresh_token_repository=RefreshTokenRepositoryImpl(),
            session_repository=SessionRepositoryImpl(),
            user_domain_service=user_domain_service,
            user_id=request.user.id,
        )
        use_case.execute(dto)

        # Determine logout message based on action
        if dto.logout_all_devices:
            logout_message = "Logout successful. All devices have been logged out."
        elif dto.device_id:
            logout_message = f"Logout successful. Device {dto.device_id} has been logged out."
        else:
            logout_message = "Logout successful. Current session has been ended."

        return helper.success(
            message=logout_message,
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="post",
    operation_summary="Forgot Password",
    operation_description="Request password reset link (email) or code (SMS).",
    request_body=ForgotPasswordSerializer,
    responses={
        200: openapi.Response(description="Password reset email/SMS sent successfully"),
        400: openapi.Response(description="Validation error"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@rate_limit(requests_per_period=3, period_seconds=300)
def forgot_password_view(request: Request) -> Response:
    """Forgot password endpoint - sends reset link/code."""
    helper = FunctionalViewHelper(request)
    serializer = ForgotPasswordSerializer(data=request.data)

    # Check validation
    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your email or phone number.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        dto = serializer.to_dto()
        use_case = ForgotPasswordUseCase(
            user_repository=UserRepositoryImpl(),
        )
        result = use_case.execute(dto)

        return helper.success(
            message=result["message"],
            data={
                "expires_in_minutes": result["expires_in_minutes"],
            },
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="post",
    operation_summary="Reset Password",
    operation_description="Reset password using token (email) or code (SMS).",
    request_body=ResetPasswordSerializer,
    responses={
        200: openapi.Response(description="Password reset successfully"),
        400: openapi.Response(description="Invalid token/code or validation error"),
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@rate_limit(requests_per_period=5, period_seconds=300)
def reset_password_view(request: Request) -> Response:
    """Reset password endpoint - validates token/code and changes password."""
    helper = FunctionalViewHelper(request)
    serializer = ResetPasswordSerializer(data=request.data)

    # Check validation
    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your reset token/code and new password.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        dto = serializer.to_dto()
        use_case = ResetPasswordUseCase(user_repository=UserRepositoryImpl())
        result = use_case.execute(dto)

        return helper.success(
            message=result["message"],
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="get",
    operation_summary="Get User Profile",
    operation_description="Get authenticated user's profile information.",
    responses={
        200: openapi.Response(description="Profile retrieved successfully"),
        401: openapi.Response(description="Unauthorized"),
    },
    tags=["Profile"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile_view(request: Request) -> Response:
    """Get user profile endpoint."""
    helper = FunctionalViewHelper(request)

    try:
        logger.info(f"Profile request for user {request.user.id}")
        use_case = GetProfileUseCase(user_repository=UserRepositoryImpl())
        user_dto = use_case.execute(request.user.id)

        from presentation.serializers.user_serializers import UserResponseSerializer

        return helper.success(
            message="Profile retrieved successfully",
            data=UserResponseSerializer.from_dto(user_dto),
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="put",
    operation_summary="Update User Profile",
    operation_description="Update authenticated user's profile information.",
    request_body=ProfileUpdateSerializer,
    responses={
        200: openapi.Response(description="Profile updated successfully"),
        400: openapi.Response(description="Validation error"),
        401: openapi.Response(description="Unauthorized"),
    },
    tags=["Profile"],
)
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_profile_view(request: Request) -> Response:
    """Update user profile endpoint."""
    helper = FunctionalViewHelper(request)
    serializer = ProfileUpdateSerializer(data=request.data)

    # Check validation
    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your profile update data.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        dto = serializer.to_dto()
        use_case = UpdateProfileUseCase(user_repository=UserRepositoryImpl())
        user_dto = use_case.execute(request.user.id, dto)

        from presentation.serializers.user_serializers import UserResponseSerializer

        return helper.success(
            message="Profile updated successfully",
            data=UserResponseSerializer.from_dto(user_dto),
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="get",
    operation_summary="Get User Sessions",
    operation_description="Get list of user sessions with pagination.",
    manual_parameters=[
        openapi.Parameter(
            "limit",
            openapi.IN_QUERY,
            description="Number of sessions per page",
            type=openapi.TYPE_INTEGER,
            default=100,
        ),
        openapi.Parameter(
            "offset",
            openapi.IN_QUERY,
            description="Number of sessions to skip",
            type=openapi.TYPE_INTEGER,
            default=0,
        ),
    ],
    responses={
        200: openapi.Response(description="Sessions retrieved successfully"),
        401: openapi.Response(description="Unauthorized"),
    },
    tags=["Profile"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_sessions_view(request: Request) -> Response:
    """Get user sessions endpoint."""
    helper = FunctionalViewHelper(request)

    try:
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))

        use_case = GetUserSessionsUseCase(
            session_repository=SessionRepositoryImpl(),
            user_id=request.user.id,
        )
        sessions = use_case.execute(limit=limit, offset=offset)

        return helper.success(
            message="Sessions retrieved successfully",
            data=[
                {
                    "id": str(session.id),
                    "device_id": session.device_id,
                    "device_name": session.device_name,
                    "device_type": session.device_type,
                    "start_time": session.start_time.isoformat(),
                    "end_time": session.end_time.isoformat() if session.end_time else None,
                    "duration_seconds": session.duration_seconds,
                    "is_active": session.is_active,
                    "ip_address": session.ip_address,
                    "user_agent": session.user_agent,
                    "created_at": session.created_at.isoformat(),
                }
                for session in sessions
            ],
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        return helper.handle_exception(e)
