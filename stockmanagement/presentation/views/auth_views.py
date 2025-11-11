"""Authentication API views."""

from __future__ import annotations

import logging
from typing import Any

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

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
from presentation.serializers.response_serializers import (
    get_error_response_schema,
    get_success_response_schema,
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
        201: openapi.Response(
            description="User created successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "message": openapi.Schema(type=openapi.TYPE_STRING),
                    "data": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "user": openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "id": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_UUID),
                                    "email": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL),
                                    "name": openapi.Schema(type=openapi.TYPE_STRING),
                                    "role": openapi.Schema(type=openapi.TYPE_STRING),
                                },
                            ),
                        },
                    ),
                    "status_code": openapi.Schema(type=openapi.TYPE_INTEGER),
                },
            ),
        ),
        400: openapi.Response(
            description="Validation error",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "success": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "error": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "code": openapi.Schema(type=openapi.TYPE_STRING),
                            "message": openapi.Schema(type=openapi.TYPE_STRING),
                            "details": openapi.Schema(type=openapi.TYPE_OBJECT),
                        },
                    ),
                    "status_code": openapi.Schema(type=openapi.TYPE_INTEGER),
                },
            ),
        ),
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
    
    # Check validation
    validation_error = helper.handle_serializer_validation(
        serializer=serializer,
        message="Validation failed. Please check your input.",
        code="VALIDATION_ERROR",
    )
    if validation_error:
        logger.warning(
            f"Signup validation failed - email: {request.data.get('email', 'N/A')}",
            extra={"errors": serializer.errors}
        )
        return validation_error

    try:
        dto = serializer.to_dto()
        logger.debug(f"Creating user with email: {dto.email}, role: {dto.role}")
        use_case = CreateUserUseCase(user_repository=UserRepositoryImpl())
        user_dto = use_case.execute(dto)
        logger.info(f"User created successfully - ID: {user_dto.id}, email: {user_dto.email}")

        # Send OTP automatically on signup
        if user_dto.email:
            try:
                logger.debug(f"Sending OTP to email: {user_dto.email}")
                otp_use_case = RequestOTPUseCase(
                    otp_repository=OTPRepositoryImpl(),
                    user_repository=UserRepositoryImpl(),
                )
                otp_request_dto = OTPRequestDTO(
                    email=user_dto.email,
                    otp_type="email",
                )
                otp_result = otp_use_case.execute(otp_request_dto)
                logger.info(
                    f"OTP sent successfully to {user_dto.email} - "
                    f"expires in {otp_result.get('expires_in_minutes')} minutes"
                )
            except Exception as otp_error:
                logger.error(
                    f"Failed to send OTP on signup for user {user_dto.id} ({user_dto.email}): {str(otp_error)}",
                    exc_info=True,
                    extra={"user_id": str(user_dto.id), "email": user_dto.email}
                )

        return helper.success(
            message="User created successfully. Please verify OTP to activate your account.",
            data={
                "user": {
                    "id": str(user_dto.id),
                    "email": user_dto.email,
                    "name": user_dto.name,
                    "role": user_dto.role,
                }
            },
            status_code=status.HTTP_201_CREATED,
        )
    except Exception as e:
        return helper.handle_exception(e)


@swagger_auto_schema(
    method="post",
    operation_summary="User Login",
    operation_description="Login with email+password or phone+password. Verifies credentials and sends OTP. Use verify-otp endpoint to complete login.",
    request_body=LoginSerializer,
    responses={
        200: openapi.Response(
            description="Credentials verified, OTP sent successfully",
            schema=get_success_response_schema(
                data_schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "expires_in_minutes": openapi.Schema(type=openapi.TYPE_INTEGER),
                    },
                ),
            ),
        ),
        400: openapi.Response(description="Invalid credentials or validation error", schema=get_error_response_schema()),
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

        # Check if user is active
        if not user.is_active:
            logger.warning(f"Login failed - inactive account: {user.id} ({identifier})")
            return helper.error(
                message="User account is not active. Please verify your OTP first.",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ACCOUNT_INACTIVE",
            )
        
        logger.debug(f"Credentials verified for user: {user.id} ({identifier})")

        # Credentials are valid, send OTP
        otp_use_case = RequestOTPUseCase(
            otp_repository=OTPRepositoryImpl(),
            user_repository=UserRepositoryImpl(),
        )
        
        # Determine OTP type based on available info
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
    operation_description="Verify OTP code and receive access/refresh tokens. For signup: activates account. For login: requires active account. Device information is registered/updated for database consistency.",
    request_body=OTPVerifySerializer,
    responses={
        200: openapi.Response(description="OTP verified successfully, tokens issued"),
        400: openapi.Response(description="Invalid or expired OTP"),
        403: openapi.Response(description="Account inactive (for login OTP)"),
    },
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

        return helper.success(
            message="OTP verified successfully. Login completed.",
            data={
                "access_token": login_response.access_token,
                "refresh_token": login_response.refresh_token,
                "expires_in": login_response.expires_in,
                "user": {
                    "id": str(login_response.user.id),
                    "email": login_response.user.email,
                    "name": login_response.user.name,
                    "role": login_response.user.role,
                    "is_active": login_response.user.is_active,
                    "avatar_url": login_response.user.avatar_url,
                },
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
    operation_description="Generate Google OAuth authorization URL. No parameters required. Signup/login is auto-detected during callback based on whether user exists.",
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
                "expires_in": response_dto.expires_in,
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
    operation_description="Exchange Google OAuth code for access token and authenticate user. Signup/login is auto-detected: if user doesn't exist, it's signup; if user exists with Google OAuth auth_method, it's login. Only 'code' parameter is required.",
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

        def generate_tokens_func(user: Any) -> dict[str, Any]:
            """Generate JWT tokens."""
            return generate_tokens(user)

        login_response = use_case.execute(dto, generate_tokens_func)

        return helper.success(
            message="Google OAuth authentication successful",
            data={
                "access_token": login_response.access_token,
                "refresh_token": login_response.refresh_token,
                "expires_in": login_response.expires_in,
                "user": {
                    "id": str(login_response.user.id),
                    "email": login_response.user.email,
                    "name": login_response.user.name,
                    "role": login_response.user.role,
                    "is_active": login_response.user.is_active,
                    "avatar_url": login_response.user.avatar_url,
                },
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
        dto = serializer.to_dto()
        user_domain_service = UserDomainService(
            user_repository=UserRepositoryImpl(),
            session_repository=SessionRepositoryImpl(),
            refresh_token_repository=RefreshTokenRepositoryImpl(),
            device_repository=DeviceRepositoryImpl(),
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

        return helper.success(
            message="Profile retrieved successfully",
            data={
                "id": str(user_dto.id),
                "email": user_dto.email,
                "name": user_dto.name,
                "phone_number": user_dto.phone_number,
                "role": user_dto.role,
                "is_active": user_dto.is_active,
                "avatar_url": user_dto.avatar_url,
                "address": user_dto.address,
                "last_login": user_dto.last_login.isoformat() if user_dto.last_login else None,
                "created_at": user_dto.created_at.isoformat(),
                "updated_at": user_dto.updated_at.isoformat(),
            },
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

        return helper.success(
            message="Profile updated successfully",
            data={
                "id": str(user_dto.id),
                "email": user_dto.email,
                "name": user_dto.name,
                "phone_number": user_dto.phone_number,
                "role": user_dto.role,
                "is_active": user_dto.is_active,
                "avatar_url": user_dto.avatar_url,
                "address": user_dto.address,
                "last_login": user_dto.last_login.isoformat() if user_dto.last_login else None,
                "created_at": user_dto.created_at.isoformat(),
                "updated_at": user_dto.updated_at.isoformat(),
            },
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

