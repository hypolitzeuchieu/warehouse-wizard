from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from django.conf import settings
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken

from application.dto.user_dto import OTPRequestDTO
from application.use_cases.business_use_cases import business_to_dto
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
    GetUserSessionsUseCase,
    LogoutUseCase,
    RefreshTokenUseCase,
    SignupUseCase,
)
from domain.users.services import UserDomainService
from infrastructure.external.google_oauth import GoogleOAuthService
from infrastructure.persistence.repositories import (
    BusinessMemberRepositoryImpl,
    BusinessRepositoryImpl,
    DeviceRepositoryImpl,
    OTPRepositoryImpl,
    PasswordResetTokenRepositoryImpl,
    RefreshTokenRepositoryImpl,
    SessionRepositoryImpl,
    UserRepositoryImpl,
)
from presentation.serializers.business_serializers import BusinessResponseSerializer
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
    UserResponseSerializer,
)
from shared.authentication.jwt import generate_tokens
from shared.authentication.jwt_blacklist_service import JWTBlacklistService
from shared.rate_limiting.decorators import get_client_ip, rate_limit
from shared.utils.device import get_or_detect_device_type
from shared.views.functional_view_helper import FunctionalViewHelper

logger = logging.getLogger(__name__)


@swagger_auto_schema(
    method="post",
    operation_summary="User Signup",
    operation_description="Create a new user account and send OTP to verify the account.",
    request_body=UserCreateSerializer,
    consumes=["multipart/form-data", "application/json"],
    responses={
        201: "User created successfully",
        400: "Bad Request",
        500: "Internal Server Error",
    },
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@parser_classes([JSONParser, FormParser, MultiPartParser])
@rate_limit(
    requests_per_period=settings.RATE_LIMIT_SIGNUP_REQUESTS,
    period_seconds=settings.RATE_LIMIT_SIGNUP_PERIOD,
)
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

        use_case = SignupUseCase(
            user_repository=UserRepositoryImpl(),
            otp_repository=OTPRepositoryImpl(),
        )
        signup_response = use_case.execute(dto)

        # Build response data
        response_data: dict[str, Any] = {
            "expires_in_minutes": signup_response.expires_in_minutes,
        }
        if signup_response.email:
            response_data["email"] = signup_response.email
        if signup_response.phone_number:
            response_data["phone_number"] = signup_response.phone_number

        return helper.success(
            message=signup_response.message,
            data=response_data,
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
@rate_limit(
    requests_per_period=settings.RATE_LIMIT_LOGIN_REQUESTS,
    period_seconds=settings.RATE_LIMIT_LOGIN_PERIOD,
)
def login_view(request: Request) -> Response:
    """User login endpoint - verifies credentials and sends OTP."""
    helper = FunctionalViewHelper(request)
    serializer = LoginSerializer(data=request.data)

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
            logger.warning(f"Login attempt with invalid identifier: {identifier}")
            return helper.error(
                message="Invalid credentials",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_CREDENTIALS",
            )

        if not UserRepositoryImpl().verify_password(user.id, dto.password):
            logger.warning(
                f"Login attempt with invalid password for user: {user.id} ({identifier})"
            )
            return helper.error(
                message="Invalid credentials",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_CREDENTIALS",
            )

        if not user.is_active:
            logger.warning(f"Login attempt for disabled account: {user.id} ({identifier})")
            return helper.error(
                message="Your account has been disabled. Please contact support.",
                status_code=status.HTTP_403_FORBIDDEN,
                code="ACCOUNT_DISABLED",
            )

        otp_use_case = RequestOTPUseCase(
            otp_repository=OTPRepositoryImpl(),
            user_repository=UserRepositoryImpl(),
        )

        otp_type = None
        otp_request_dto = None

        if dto.email:
            otp_type = "email"
            otp_request_dto = OTPRequestDTO(email=dto.email)
        elif dto.phone_number:
            otp_type = "sms"
            otp_request_dto = OTPRequestDTO(phone_number=dto.phone_number)
        else:
            # Fallback (should not happen)
            otp_type = "email"
            otp_request_dto = OTPRequestDTO(
                email=dto.email if dto.email else None,
                phone_number=dto.phone_number if dto.phone_number else None,
            )

        result = otp_use_case.execute(otp_request_dto)

        # Log OTP sent (but don't reveal if user exists)
        logger.info(
            f"OTP sent for login attempt - identifier: {identifier}, "
            f"type: {otp_type}, expires in: {result.get('expires_in_minutes')} minutes"
        )

        # Always return success message (don't reveal if user exists)
        return helper.success(
            message="OTP sent successfully. Please verify OTP to complete login.",
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
@rate_limit(
    requests_per_period=settings.RATE_LIMIT_VERIFY_OTP_REQUESTS,
    period_seconds=settings.RATE_LIMIT_VERIFY_OTP_PERIOD,
)
def verify_otp_view(request: Request) -> Response:
    """OTP verification endpoint - returns tokens after verification."""
    helper = FunctionalViewHelper(request)
    serializer = OTPVerifySerializer(data=request.data)

    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your OTP code.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        dto = serializer.to_dto()

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

        businesses_list = []
        user_role = getattr(login_response.user, "role", None)
        business_repo = BusinessRepositoryImpl()
        member_repo = BusinessMemberRepositoryImpl()

        if user_role == "owner":
            owned_businesses = business_repo.get_by_owner(login_response.user.id)
            for business in owned_businesses:
                business_dto = business_to_dto(business)
                business_data = BusinessResponseSerializer.from_dto(business_dto)
                business_data["role"] = "owner"
                businesses_list.append(business_data)
        elif user_role in ["manager", "cashier", "stock_keeper", "delivery"]:
            # Get all businesses where user is a member
            memberships = member_repo.get_user_businesses(login_response.user.id)
            for membership in memberships:
                business = business_repo.get_by_id(membership.business_id)
                if business:
                    business_dto = business_to_dto(business)
                    business_data = BusinessResponseSerializer.from_dto(business_dto)
                    business_data["role"] = membership.role
                    businesses_list.append(business_data)

        return helper.success(
            message="OTP verified successfully. Login completed.",
            data={
                "access_token": login_response.access_token,
                "refresh_token": login_response.refresh_token,
                "expires_in": login_response.expires_in,
                "user": UserResponseSerializer.from_dto(login_response.user),
                "businesses": businesses_list,
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
@rate_limit(
    requests_per_period=settings.RATE_LIMIT_REQUEST_OTP_REQUESTS,
    period_seconds=settings.RATE_LIMIT_REQUEST_OTP_PERIOD,
)
def request_otp_view(request: Request) -> Response:
    """Request OTP endpoint."""
    helper = FunctionalViewHelper(request)
    serializer = OTPRequestSerializer(data=request.data)

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
@rate_limit(
    requests_per_period=settings.RATE_LIMIT_GOOGLE_AUTH_URL_REQUESTS,
    period_seconds=settings.RATE_LIMIT_GOOGLE_AUTH_URL_PERIOD,
)
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
@rate_limit(
    requests_per_period=settings.RATE_LIMIT_GOOGLE_CALLBACK_REQUESTS,
    period_seconds=settings.RATE_LIMIT_GOOGLE_CALLBACK_PERIOD,
)
def google_callback_view(request: Request) -> Response:
    """Google OAuth callback endpoint - exchanges code for tokens."""
    helper = FunctionalViewHelper(request)
    serializer = GoogleOAuthCodeSerializer(data=request.data)

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
@rate_limit(
    requests_per_period=settings.RATE_LIMIT_REFRESH_TOKEN_REQUESTS,
    period_seconds=settings.RATE_LIMIT_REFRESH_TOKEN_PERIOD,
)
def refresh_token_view(request: Request) -> Response:
    """Refresh token endpoint."""
    helper = FunctionalViewHelper(request)
    serializer = RefreshTokenSerializer(data=request.data)

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
    operation_description="Logout user from current device or all devices.",
    request_body=LogoutSerializer,
    responses={200: "Logout successful", 400: "Validation error", 401: "Unauthorized"},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request: Request) -> Response:
    """User logout endpoint."""
    helper = FunctionalViewHelper(request)
    serializer = LogoutSerializer(data=request.data)

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
            # Get all active refresh tokens for this user (logout from all devices)
            refresh_tokens = refresh_token_repo.get_by_user_and_device(request.user.id, None)
            logger.info(
                f"Logout all devices - blacklisting all refresh tokens for user {request.user.id}"
            )
        elif dto.device_id:
            # Get refresh tokens for specific device
            refresh_tokens = refresh_token_repo.get_by_user_and_device(
                request.user.id, dto.device_id
            )
            logger.info(
                f"Logout device {dto.device_id} - blacklisting refresh tokens for user {request.user.id}"
            )
        else:
            refresh_tokens = []
            logger.info(
                f"Logout current session - access token already blacklisted for user {request.user.id}"
            )

        for refresh_token_entity in refresh_tokens:
            if refresh_token_entity.token and not refresh_token_entity.revoked:
                try:
                    JWTBlacklistService.blacklist_refresh_token(
                        refresh_token_string=refresh_token_entity.token,
                        user_id=request.user.id,
                        blacklist_access_token=True,
                    )
                    logger.info(
                        f"Refresh token and associated access tokens blacklisted "
                        f"for user {request.user.id}"
                    )
                except Exception as refresh_token_error:
                    logger.warning(
                        f"Failed to blacklist refresh token {refresh_token_entity.id}: "
                        f"{str(refresh_token_error)}. Continuing with logout anyway.",
                        exc_info=True,
                    )

        use_case = LogoutUseCase(
            refresh_token_repository=RefreshTokenRepositoryImpl(),
            session_repository=SessionRepositoryImpl(),
            user_domain_service=user_domain_service,
            user_id=request.user.id,
        )
        use_case.execute(dto)
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
    responses={200: "Password reset email/SMS sent successfully", 400: "Validation error"},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@rate_limit(
    requests_per_period=settings.RATE_LIMIT_FORGOT_PASSWORD_REQUESTS,
    period_seconds=settings.RATE_LIMIT_FORGOT_PASSWORD_PERIOD,
)
def forgot_password_view(request: Request) -> Response:
    """Forgot password endpoint - sends reset link/code."""
    helper = FunctionalViewHelper(request)
    serializer = ForgotPasswordSerializer(data=request.data)

    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your identifier (email or phone number).",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        dto = serializer.to_dto()
        use_case = ForgotPasswordUseCase(
            user_repository=UserRepositoryImpl(),
            password_reset_token_repository=PasswordResetTokenRepositoryImpl(),
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
    operation_description=(
        "Reset password using token (email) or code (SMS). "
        "The reset type is determined automatically: token = email, code = SMS. "
        "Email/phone_number are extracted from the token/code automatically."
    ),
    request_body=ResetPasswordSerializer,
    responses={200: "Password reset successfully", 400: "Invalid token/code or validation error"},
    tags=["Authentication"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@rate_limit(
    requests_per_period=settings.RATE_LIMIT_RESET_PASSWORD_REQUESTS,
    period_seconds=settings.RATE_LIMIT_RESET_PASSWORD_PERIOD,
)
def reset_password_view(request: Request) -> Response:
    """Reset password endpoint - validates token/code and changes password."""
    helper = FunctionalViewHelper(request)
    serializer = ResetPasswordSerializer(data=request.data)

    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your reset token/code and new password.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        return validation_error

    try:
        dto = serializer.to_dto()
        use_case = ResetPasswordUseCase(
            user_repository=UserRepositoryImpl(),
            password_reset_token_repository=PasswordResetTokenRepositoryImpl(),
        )
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
