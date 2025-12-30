"""Business use cases."""

import logging
import os
from uuid import UUID, uuid4

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from application.dto.business_dto import (
    BusinessCreateDTO,
    BusinessMemberCreateDTO,
    BusinessMemberResponseDTO,
    BusinessResponseDTO,
    BusinessUpdateDTO,
)
from domain.business.entities import Business, BusinessMember
from domain.business.repositories import (
    BusinessMemberRepository,
    BusinessRepository,
)
from domain.business.services import BusinessDomainService
from domain.subscription.entities import Subscription, SubscriptionPlan
from domain.subscription.repositories import (
    SubscriptionPlanRepository,
    SubscriptionRepository,
)
from domain.users.entities import AuthMethod, User, UserRole
from domain.users.repositories import UserRepository
from shared.exceptions.specific import BadRequestError, ForbiddenError, NotFoundError
from shared.services.qr_code_service import QRCodeService
from shared.services.s3_service import S3Service
from shared.utils.password_generator import generate_secure_password
from shared.utils.validation import validate_business_access
from tasks.member_tasks import (
    send_member_credentials_email_task,
    send_member_credentials_sms_task,
)

logger = logging.getLogger(__name__)


def _normalize_uuid(value: UUID | str | None) -> UUID | None:
    """Normalize UUID value to UUID type."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def _compare_uuids(uuid1: UUID | str | None, uuid2: UUID | str | None) -> bool:
    """Compare two UUIDs safely, handling UUID and string types."""
    normalized1 = _normalize_uuid(uuid1)
    normalized2 = _normalize_uuid(uuid2)

    if normalized1 is None or normalized2 is None:
        return False

    return normalized1 == normalized2


def _get_subscription_and_plan(
    business: Business,
    subscription_repository: SubscriptionRepository | None = None,
    plan_repository: SubscriptionPlanRepository | None = None,
) -> tuple["Subscription | None", "SubscriptionPlan | None"]:
    """
    Get subscription and plan for a business.

    Args:
        business: Business entity
        subscription_repository: Optional subscription repository
        plan_repository: Optional subscription plan repository

    Returns:
        Tuple of (subscription, plan) or (None, None) if not found
    """
    if (
        not business.subscription_id
        or not subscription_repository
        or not plan_repository
    ):
        return None, None

    try:
        subscription = subscription_repository.get_by_id(business.subscription_id)
        if subscription:
            plan = plan_repository.get_by_id(subscription.plan_id)
            return subscription, plan
    except Exception:
        logger.warning(f"Failed to get subscription for business {business.id}")

    return None, None


def _business_to_dto(
    business: Business,
    subscription: "Subscription | None" = None,
    plan: "SubscriptionPlan | None" = None,
) -> BusinessResponseDTO:
    """
    Convert business entity to DTO (shared utility function).

    Args:
        business: Business entity
        subscription: Optional subscription entity associated with the business
        plan: Optional subscription plan entity (required if subscription is provided)
    """
    qr_code_url = business.qr_code_url
    logo_url = business.logo_url

    try:
        s3 = S3Service()
        if qr_code_url:
            qr_code_url = (
                s3.generate_presigned_get_url(qr_code_url, expires_in=86400)
                or qr_code_url
            )
        if logo_url:
            logo_url = (
                s3.generate_presigned_get_url(logo_url, expires_in=86400) or logo_url
            )
    except Exception:
        pass

    subscription_data = None
    if subscription:
        plan_data = None
        if plan:
            plan_data = {
                "id": str(plan.id),
                "name": plan.name,
                "code": plan.code,
            }

        subscription_data = {
            "id": str(subscription.id),
            "status": subscription.status.value,
            "start_date": (
                subscription.start_date.isoformat() if subscription.start_date else None
            ),
            "end_date": (
                subscription.end_date.isoformat() if subscription.end_date else None
            ),
            "cancelled_at": (
                subscription.cancelled_at.isoformat()
                if subscription.cancelled_at
                else None
            ),
            "updated_at": (
                subscription.updated_at.isoformat() if subscription.updated_at else None
            ),
            "billing_period": subscription.billing_period.value,
            "plan": plan_data,
        }

    return BusinessResponseDTO(
        id=business.id,
        name=business.name,
        unique_name=business.unique_name,
        owner_id=business.owner_id,
        description=business.description,
        address=business.address,
        phone_number=business.phone_number,
        email=business.email,
        qr_code_url=qr_code_url,
        logo_url=logo_url,
        is_active=business.is_active,
        settings=business.settings,
        created_at=business.created_at,
        updated_at=business.updated_at,
        subscription=subscription_data,
    )


class CreateBusinessUseCase:
    """Use case for creating a business."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        user_repository: UserRepository,
        business_member_repository: BusinessMemberRepository,
        owner_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.business_repository = business_repository
        self.user_repository = user_repository
        self.business_member_repository = business_member_repository
        self.owner_id = owner_id

    @transaction.atomic
    def execute(self, dto: BusinessCreateDTO) -> BusinessResponseDTO:
        """Execute business creation."""
        user = self.user_repository.get_by_id(self.owner_id)
        if not user:
            raise NotFoundError(
                detail="User not found",
                code="USER_NOT_FOUND",
            )

        if not user.is_active:
            raise ForbiddenError(
                detail="User account is not active. Please verify your Account first.",
                code="ACCOUNT_INACTIVE",
            )

        if not user.email_verified:
            raise BadRequestError(
                detail="User account is not verified. Please verify your Account before creating a business.",
                code="ACCOUNT_NOT_VERIFIED",
            )

        user_businesses = self.business_member_repository.get_user_businesses(
            self.owner_id
        )
        if user_businesses:
            raise BadRequestError(
                detail="You cannot create a business while being a member of another business. Please leave your current business first.",
                code="MEMBER_CANNOT_CREATE_BUSINESS",
            )

        unique_name = dto.unique_name
        if not unique_name:
            base = slugify(dto.name) or "business"
            base = base.lower().strip("-")
            base = base[:60].strip("-")

            for _ in range(10):
                candidate = f"{base}-{uuid4().hex[:12]}"
                if not self.business_repository.get_by_unique_name(candidate):
                    unique_name = candidate
                    break

            if not unique_name:
                raise BadRequestError(
                    detail="Failed to generate a unique business identifier. Please try again.",
                    code="UNIQUE_NAME_GENERATION_FAILED",
                )

        existing = self.business_repository.get_by_unique_name(unique_name)
        if existing:
            raise BadRequestError(
                detail="Business with this unique name already exists",
                code="UNIQUE_NAME_EXISTS",
            )

        business = Business(
            id=uuid4(),
            name=dto.name,
            unique_name=unique_name,
            owner_id=self.owner_id,
            description=dto.description,
            address=dto.address,
            phone_number=dto.phone_number,
            email=dto.email,
            qr_code_url=None,
            logo_url=None,
            is_active=False,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            settings=dto.settings or {},
        )

        business = self.business_repository.create(business)
        logger.info(
            f"Business created - business_id: {business.id}, "
            f"unique_name: {business.unique_name}, owner_id: {self.owner_id}"
        )

        try:
            if getattr(dto, "logo_file", None):
                s3 = S3Service()
                logo_file = dto.logo_file
                logo_file.content_type = (
                    getattr(logo_file, "content_type", None) or "image/png"
                )
                uploaded_logo_url = s3.upload_logo(
                    file=logo_file,
                    business_id=str(business.id),
                    business_name=business.unique_name or business.name,
                )
                business.logo_url = uploaded_logo_url
                business = self.business_repository.update(business)
                logger.info(f"Logo uploaded for business {business.id}")
            elif getattr(dto, "logo_url", None):
                business.logo_url = dto.logo_url
                business = self.business_repository.update(business)
                logger.info(f"Logo URL set for business {business.id}")
        except Exception as e:
            logger.warning(f"Failed to set logo for business {business.id}: {str(e)}")

        if user.role != UserRole.OWNER:
            user.role = UserRole.OWNER
            user.updated_at = timezone.now()
            self.user_repository.update(user)

        try:
            qr_service = QRCodeService()
            base_url = os.getenv("BASE_URL", "https://maahbusiness.com")
            qr_code_url = qr_service.upload_business_qr_code(
                business.id,
                business_name=business.unique_name or business.name,
                base_url=base_url,
            )
            business.qr_code_url = qr_code_url
            business = self.business_repository.update(business)
            logger.info(f"QR code generated and uploaded for business {business.id}")
        except Exception as e:
            logger.warning(
                f"Failed to generate QR code for business {business.id}: {str(e)}"
            )

        return self._to_dto(business)

    def _to_dto(self, business: Business) -> BusinessResponseDTO:
        """Convert business entity to DTO."""
        return _business_to_dto(business, subscription=None, plan=None)


class UpdateBusinessUseCase:
    """Use case for updating a business."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        subscription_repository: SubscriptionRepository | None = None,
        plan_repository: SubscriptionPlanRepository | None = None,
    ) -> None:
        """Initialize use case."""
        self.business_repository = business_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.subscription_repository = subscription_repository
        self.plan_repository = plan_repository

    def execute(self, dto: BusinessUpdateDTO) -> BusinessResponseDTO:
        """Execute business update."""
        business = self.business_repository.get_by_id(self.business_id)
        if not business:
            raise NotFoundError(
                detail="Business not found",
                code="BUSINESS_NOT_FOUND",
            )

        if not self.business_domain_service.can_user_manage_members(
            self.business_id, self.user_id
        ):
            raise ForbiddenError(
                detail="You don't have permission to update this business",
                code="PERMISSION_DENIED",
            )

        if dto.name is not None:
            business.name = dto.name
        if dto.description is not None:
            business.description = dto.description
        if dto.address is not None:
            business.address = dto.address
        if dto.phone_number is not None:
            business.phone_number = dto.phone_number
        if dto.email is not None:
            business.email = dto.email
        if dto.logo_url is not None:
            business.logo_url = dto.logo_url
        if dto.settings is not None:
            business.settings = dto.settings
        business.updated_at = timezone.now()

        business = self.business_repository.update(business)
        return self._to_dto(business)

    def _to_dto(self, business: Business) -> BusinessResponseDTO:
        """Convert business entity to DTO."""
        subscription, plan = _get_subscription_and_plan(
            business, self.subscription_repository, self.plan_repository
        )
        return _business_to_dto(business, subscription=subscription, plan=plan)


class DeleteBusinessUseCase:
    """Use case for deleting a business."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.business_repository = business_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self) -> None:
        """Execute business deletion."""
        if not self.business_domain_service.can_user_delete_business(
            self.business_id, self.user_id
        ):
            raise ForbiddenError(
                detail="Only the owner can delete the business",
                code="PERMISSION_DENIED",
            )

        self.business_repository.delete(self.business_id)

        logger.info(
            f"Business deleted - business_id: {self.business_id}, "
            f"deleted_by: {self.user_id}"
        )


class AddBusinessMemberUseCase:
    """Use case for adding a business member."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        business_member_repository: BusinessMemberRepository,
        business_domain_service: BusinessDomainService,
        user_repository: UserRepository,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.business_repository = business_repository
        self.business_member_repository = business_member_repository
        self.business_domain_service = business_domain_service
        self.user_repository = user_repository
        self.business_id = business_id
        self.user_id = user_id

    @transaction.atomic
    def execute(self, dto: BusinessMemberCreateDTO) -> BusinessMemberResponseDTO:
        """Execute adding business member."""
        business = self.business_repository.get_by_id(self.business_id)
        if not business:
            raise NotFoundError(
                detail="Business not found",
                code="BUSINESS_NOT_FOUND",
            )
        if not business.is_active:
            raise ForbiddenError(
                detail="Business is not active",
                code="BUSINESS_NOT_ACTIVE",
            )
        if not self.business_domain_service.can_user_manage_members(
            self.business_id, self.user_id
        ):
            raise ForbiddenError(
                detail="You don't have permission to add members",
                code="PERMISSION_DENIED",
            )

        if dto.role == "owner":
            raise BadRequestError(
                detail="Cannot create a member with owner role",
                code="INVALID_ROLE",
            )

        if dto.role == "manager":
            if not self.business_domain_service.can_user_manage_managers(
                self.business_id, self.user_id
            ):
                raise ForbiddenError(
                    detail="Only the owner can add managers",
                    code="PERMISSION_DENIED",
                )

        target_user = None
        user_created = False
        generated_password = None
        found_by = None
        if dto.user_id:
            target_user = self.user_repository.get_by_id(dto.user_id)
            if not target_user:
                raise NotFoundError(
                    detail="User not found",
                    code="USER_NOT_FOUND",
                )
            found_by = "user_id"
            if not target_user.email_verified:
                raise BadRequestError(
                    detail="User account is not verified",
                    code="USER_NOT_VERIFIED",
                )
            if target_user.role == UserRole.OWNER:
                raise BadRequestError(
                    detail="Business owners cannot be added as members",
                    code="OWNER_CANNOT_BE_MEMBER",
                )
            if not target_user.is_active:
                raise BadRequestError(
                    detail="User account is not active",
                    code="USER_NOT_ACTIVE",
                )
        else:
            target_user = None

            if dto.email:
                target_user = self.user_repository.get_by_email(dto.email)
                if target_user:
                    found_by = "email"

            if not target_user and dto.phone_number:
                target_user = self.user_repository.get_by_phone_number(dto.phone_number)
                if target_user:
                    found_by = "phone_number"

            if target_user:
                if not target_user.email_verified:
                    raise BadRequestError(
                        detail="User account is not verified",
                        code="USER_NOT_VERIFIED",
                    )
                if target_user.role == UserRole.OWNER:
                    raise BadRequestError(
                        detail="Business owners cannot be added as members",
                        code="OWNER_CANNOT_BE_MEMBER",
                    )
                if not target_user.is_active:
                    raise BadRequestError(
                        detail="User account is not active",
                        code="USER_NOT_ACTIVE",
                    )
            else:
                if not dto.name:
                    raise BadRequestError(
                        detail="Name is required when creating a new user",
                        code="NAME_REQUIRED",
                    )

                existing_user_by_email = None
                existing_user_by_phone = None

                if dto.email:
                    existing_user_by_email = self.user_repository.get_by_email(
                        dto.email
                    )
                if dto.phone_number:
                    existing_user_by_phone = self.user_repository.get_by_phone_number(
                        dto.phone_number
                    )

                if existing_user_by_email and existing_user_by_phone:
                    if existing_user_by_email.id != existing_user_by_phone.id:
                        raise BadRequestError(
                            detail="Email and phone number belong to different users. Please provide matching credentials.",
                            code="CREDENTIALS_MISMATCH",
                        )

                if existing_user_by_email:
                    raise BadRequestError(
                        detail=f"A member with email '{dto.email}' already exists",
                        code="MEMBER_EMAIL_ALREADY_EXISTS",
                    )
                if existing_user_by_phone:
                    raise BadRequestError(
                        detail=f"A member with phone number '{dto.phone_number}' already exists",
                        code="MEMBER_PHONE_ALREADY_EXISTS",
                    )

                generated_password = dto.password or generate_secure_password()

                name = dto.name

                target_user = User(
                    id=uuid4(),
                    email=dto.email,
                    name=name,
                    phone_number=dto.phone_number,
                    role=UserRole.CUSTOMER,
                    is_active=True,
                    email_verified=True,
                    is_staff=False,
                    is_superuser=False,
                    last_login=None,
                    created_at=timezone.now(),
                    updated_at=timezone.now(),
                    address=None,
                    avatar_url=None,
                    auth_method=(
                        AuthMethod.EMAIL_PASSWORD if dto.email else AuthMethod.PHONE_OTP
                    ),
                )

                try:
                    target_user = self.user_repository.create(
                        target_user, password=generated_password
                    )
                    user_created = True
                except IntegrityError as e:
                    error_message = str(e).lower()
                    if "email" in error_message or (
                        "unique constraint" in error_message
                        and "email" in error_message
                    ):
                        raise BadRequestError(
                            detail=f"A member with email '{dto.email}' already exists. This email is used for login and cannot be duplicated.",
                            code="MEMBER_EMAIL_ALREADY_EXISTS",
                        ) from e
                    elif (
                        "phone_number" in error_message
                        or "phone" in error_message
                        or (
                            "unique constraint" in error_message
                            and "phone" in error_message
                        )
                    ):
                        raise BadRequestError(
                            detail=f"A member with phone number '{dto.phone_number}' already exists. This phone number is used for login and cannot be duplicated.",
                            code="MEMBER_PHONE_ALREADY_EXISTS",
                        ) from e
                    else:
                        conflict_fields = []
                        if dto.email:
                            conflict_fields.append(f"email '{dto.email}'")
                        if dto.phone_number:
                            conflict_fields.append(f"phone number '{dto.phone_number}'")

                        detail_msg = f"A member with {' or '.join(conflict_fields)} already exists. These credentials are used for login and cannot be duplicated."
                        raise BadRequestError(
                            detail=detail_msg,
                            code="MEMBER_CREDENTIALS_ALREADY_EXISTS",
                        ) from e

        existing_members = self.business_member_repository.get_business_members(
            self.business_id, active_only=False
        )
        if any(member.user_id == target_user.id for member in existing_members):
            existing_member = next(
                (m for m in existing_members if m.user_id == target_user.id), None
            )
            if (
                existing_member
                and existing_member.is_active
                and existing_member.left_at is None
            ):
                if found_by == "email":
                    detail_message = f"User with email '{dto.email}' is already a member of this business"
                elif found_by == "phone_number":
                    detail_message = f"User with phone number '{dto.phone_number}' is already a member of this business"
                elif found_by == "user_id":
                    detail_message = f"User with ID '{dto.user_id}' is already a member of this business"
                else:
                    detail_message = "User is already a member of this business"
            else:
                if found_by == "email":
                    detail_message = f"User with email '{dto.email}' was previously a member of this business. Please reactivate the existing membership instead of creating a new one."
                elif found_by == "phone_number":
                    detail_message = f"User with phone number '{dto.phone_number}' was previously a member of this business. Please reactivate the existing membership instead of creating a new one."
                elif found_by == "user_id":
                    detail_message = f"User with ID '{dto.user_id}' was previously a member of this business. Please reactivate the existing membership instead of creating a new one."
                else:
                    detail_message = "User was previously a member of this business. Please reactivate the existing membership instead of creating a new one."

            raise BadRequestError(
                detail=detail_message,
                code="USER_ALREADY_MEMBER",
            )

        user_businesses = self.business_member_repository.get_user_businesses(
            target_user.id
        )
        if user_businesses:
            raise BadRequestError(
                detail="User is already a member of another business. A user can only be a member of one business.",
                code="USER_ALREADY_MEMBER_OF_OTHER_BUSINESS",
            )

        member = BusinessMember(
            id=uuid4(),
            business_id=self.business_id,
            user_id=target_user.id,
            role=dto.role,
            is_active=True,
            joined_at=timezone.now(),
            left_at=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
        )

        try:
            member = self.business_member_repository.create(member)
        except IntegrityError as e:
            error_message = str(e).lower()
            if (
                "business" in error_message and "user" in error_message
            ) or "unique constraint" in error_message:
                if found_by == "email":
                    detail_message = f"User with email '{dto.email}' is already associated with this business (may be inactive). Please reactivate the existing membership."
                elif found_by == "phone_number":
                    detail_message = f"User with phone number '{dto.phone_number}' is already associated with this business (may be inactive). Please reactivate the existing membership."
                elif found_by == "user_id":
                    detail_message = f"User with ID '{dto.user_id}' is already associated with this business (may be inactive). Please reactivate the existing membership."
                else:
                    detail_message = "User is already associated with this business (may be inactive). Please reactivate the existing membership."

                raise BadRequestError(
                    detail=detail_message,
                    code="USER_ALREADY_MEMBER",
                ) from e
            else:
                raise

        if user_created and generated_password:
            business = self.business_repository.get_by_id(self.business_id)
            business_name = business.name if business else "the business"

            credentials_sent = False
            logger.info(
                f"Business member added - member_id: {member.id}, "
                f"user_id: {target_user.id}, business_id: {self.business_id}, "
                f"role: {dto.role}, added_by: {self.user_id}, user_created: {user_created}"
            )

            if target_user.email:
                try:
                    send_member_credentials_email_task.delay(
                        email=target_user.email,
                        username=target_user.name,
                        password=generated_password,
                        business_name=business_name,
                        role=dto.role,
                    )
                    logger.info(
                        f"Member credentials email task queued for {target_user.email} "
                        f"(user_id: {target_user.id}, business_id: {self.business_id})"
                    )
                    credentials_sent = True
                except ConnectionError as celery_error:
                    logger.error(
                        f"Failed to queue member credentials email task for {target_user.email}: "
                        f"{str(celery_error)}. Please ensure Celery worker is running.",
                        exc_info=True,
                        extra={
                            "user_id": str(target_user.id),
                            "business_id": str(self.business_id),
                            "email": target_user.email,
                        },
                    )

            if not credentials_sent and target_user.phone_number:
                try:
                    send_member_credentials_sms_task.delay(
                        phone_number=target_user.phone_number,
                        username=target_user.name,
                        password=generated_password,
                        business_name=business_name,
                        role=dto.role,
                        email=target_user.email,
                    )
                    logger.info(
                        f"Member credentials SMS task queued for {target_user.phone_number} "
                        f"(user_id: {target_user.id}, business_id: {self.business_id})"
                    )
                    credentials_sent = True
                except ConnectionError as celery_error:
                    logger.error(
                        f"Failed to queue member credentials SMS task for {target_user.phone_number}: "
                        f"{str(celery_error)}. Please ensure Celery worker is running.",
                        exc_info=True,
                        extra={
                            "user_id": str(target_user.id),
                            "business_id": str(self.business_id),
                            "phone_number": target_user.phone_number,
                        },
                    )

            if not credentials_sent:
                logger.warning(
                    f"Could not send credentials to user {target_user.id} - "
                    f"no email or phone number available or Celery not available"
                )

        return self._to_dto(member, credentials=None)

    def _to_dto(
        self, member: BusinessMember, credentials: dict | None = None
    ) -> BusinessMemberResponseDTO:
        """Convert business member entity to DTO."""
        return BusinessMemberResponseDTO(
            id=member.id,
            business_id=member.business_id,
            user_id=member.user_id,
            role=member.role,
            is_active=member.is_active,
            joined_at=member.joined_at,
            left_at=member.left_at,
            created_at=member.created_at,
            updated_at=member.updated_at,
            credentials=credentials,
        )


class RemoveBusinessMemberUseCase:
    """Use case for removing a business member."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        business_member_repository: BusinessMemberRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
    ) -> None:
        """Initialize use case."""
        self.business_repository = business_repository
        self.business_member_repository = business_member_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id

    def execute(self, member_id: UUID) -> None:
        """Execute removing business member."""
        if not self.business_domain_service.can_user_manage_members(
            self.business_id, self.user_id
        ):
            raise ForbiddenError(
                detail="You don't have permission to remove members",
                code="PERMISSION_DENIED",
            )
        business = self.business_repository.get_by_id(self.business_id)
        if not business:
            raise NotFoundError(
                detail="Business not found",
                code="BUSINESS_NOT_FOUND",
            )
        if not business.is_active:
            raise BadRequestError(
                detail="Cannot remove members from an inactive business",
                code="BUSINESS_INACTIVE",
            )

        member = self.business_member_repository.get_by_id(member_id)
        if not member:
            raise NotFoundError(
                detail="Member not found",
                code="MEMBER_NOT_FOUND",
            )
        if not _compare_uuids(member.business_id, self.business_id):
            raise ForbiddenError(
                detail="Member does not belong to this business",
                code="MEMBER_NOT_IN_BUSINESS",
            )
        if not member.is_active or member.left_at is not None:
            raise BadRequestError(
                detail="Member is already inactive or has been removed",
                code="MEMBER_ALREADY_INACTIVE",
            )
        if member.is_manager():
            if not self.business_domain_service.can_user_manage_managers(
                self.business_id, self.user_id
            ):
                raise ForbiddenError(
                    detail="Only the owner can remove managers",
                    code="PERMISSION_DENIED",
                )

        self.business_member_repository.remove(member_id)

        logger.info(
            f"Business member removed - member_id: {member_id}, "
            f"removed_by: {self.user_id}"
        )


class ListBusinessMembersUseCase:
    """Use case for listing business members."""

    def __init__(
        self,
        business_member_repository: BusinessMemberRepository,
        business_domain_service: BusinessDomainService,
        user_repository: UserRepository | None,
        business_id: UUID,
        user_id: UUID,
        include_inactive: bool = False,
    ) -> None:
        """Initialize use case."""
        self.business_member_repository = business_member_repository
        self.business_domain_service = business_domain_service
        self.user_repository = user_repository
        self.business_id = business_id
        self.user_id = user_id
        self.include_inactive = include_inactive

    def execute(self) -> list[BusinessMemberResponseDTO]:
        """Execute listing business members."""
        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        members = self.business_member_repository.get_business_members(
            self.business_id, active_only=not self.include_inactive
        )
        logger.info(f"Fetched {members} members for business {self.business_id}")

        return [self._to_dto(member) for member in members]

    def _to_dto(self, member: BusinessMember) -> BusinessMemberResponseDTO:
        """Convert business member entity to DTO with optional user details."""
        user_details: dict | None = None
        if self.user_repository:
            user = self.user_repository.get_by_id(member.user_id)
            if user:
                avatar_url = user.avatar_url
                try:
                    if avatar_url:
                        avatar_url = (
                            S3Service().generate_presigned_get_url(
                                avatar_url, expires_in=86400
                            )
                            or avatar_url
                        )
                except Exception:
                    pass
                user_details = {
                    "id": str(user.id),
                    "name": user.name,
                    "email": user.email,
                    "phone_number": user.phone_number,
                    "role": (
                        user.role.value
                        if hasattr(user.role, "value")
                        else str(user.role)
                    ),
                    "avatar_url": avatar_url,
                    "is_active": user.is_active,
                }
            else:
                logger.warning(
                    f"User {member.user_id} not found for business member {member.id}"
                )

        return BusinessMemberResponseDTO(
            id=member.id,
            business_id=member.business_id,
            user_id=member.user_id,
            role=member.role,
            is_active=member.is_active,
            joined_at=member.joined_at,
            left_at=member.left_at,
            created_at=member.created_at,
            updated_at=member.updated_at,
            user=user_details,
        )


class GetBusinessUseCase:
    """Use case for getting a business by ID."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        business_domain_service: BusinessDomainService,
        business_id: UUID,
        user_id: UUID,
        subscription_repository: SubscriptionRepository | None = None,
        plan_repository: SubscriptionPlanRepository | None = None,
    ) -> None:
        """Initialize use case."""
        self.business_repository = business_repository
        self.business_domain_service = business_domain_service
        self.business_id = business_id
        self.user_id = user_id
        self.subscription_repository = subscription_repository
        self.plan_repository = plan_repository

    def execute(self) -> BusinessResponseDTO:
        """Execute getting business."""
        business = self.business_repository.get_by_id(self.business_id)
        if not business:
            raise NotFoundError(
                detail="Business not found",
                code="BUSINESS_NOT_FOUND",
            )

        validate_business_access(
            business_domain_service=self.business_domain_service,
            business_id=self.business_id,
            user_id=self.user_id,
        )

        return self._to_dto(business)

    def _to_dto(self, business: Business) -> BusinessResponseDTO:
        """Convert business entity to DTO."""
        subscription, plan = _get_subscription_and_plan(
            business, self.subscription_repository, self.plan_repository
        )
        return _business_to_dto(business, subscription=subscription, plan=plan)


class ListBusinessesUseCase:
    """Use case for listing businesses for a user."""

    def __init__(
        self,
        business_repository: BusinessRepository,
        business_member_repository: BusinessMemberRepository,
        user_id: UUID,
        subscription_repository: SubscriptionRepository | None = None,
        plan_repository: SubscriptionPlanRepository | None = None,
    ) -> None:
        """Initialize use case."""
        self.business_repository = business_repository
        self.business_member_repository = business_member_repository
        self.user_id = user_id
        self.subscription_repository = subscription_repository
        self.plan_repository = plan_repository

    def execute(self) -> list[BusinessResponseDTO]:
        """Execute listing businesses."""
        owned_businesses = self.business_repository.get_by_owner(self.user_id)

        member_businesses = self.business_member_repository.get_user_businesses(
            self.user_id
        )

        all_businesses: list[Business] = list(owned_businesses)
        for member in member_businesses:
            business = self.business_repository.get_by_id(member.business_id)
            if business and business.id not in {b.id for b in all_businesses}:
                all_businesses.append(business)

        result = []
        for business in all_businesses:
            subscription, plan = _get_subscription_and_plan(
                business, self.subscription_repository, self.plan_repository
            )
            result.append(
                _business_to_dto(business, subscription=subscription, plan=plan)
            )

        return result
