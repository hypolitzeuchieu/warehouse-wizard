"""OTP repository implementations."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from django.db.models import Q
from django.utils import timezone

from domain.users.entities import OTP as OTPEntity
from domain.users.repositories import OTPRepository
from infrastructure.persistence.models.otp_models import OTP as OTPModel


class OTPRepositoryImpl(OTPRepository):
    """OTP repository implementation."""

    def create(self, otp: OTPEntity) -> OTPEntity:
        """Create a new OTP."""
        from django.utils import timezone
        
        otp_model = OTPModel.objects.create(
            id=otp.id,
            user_id=otp.user_id,
            email=otp.email,
            phone_number=otp.phone_number,
            otp_code=otp.otp_code,
            otp_type=otp.otp_type,
            purpose=otp.purpose,
            expires_at=otp.expires_at,
            verified=otp.verified,
            verified_at=otp.verified_at,
            attempts=otp.attempts,
            max_attempts=otp.max_attempts,
            created_at=otp.created_at,
            updated_at=otp.updated_at,
        )
        return self._to_domain_entity(otp_model)

    def get_by_id(self, otp_id: UUID) -> Optional[OTPEntity]:
        """Get OTP by ID."""
        try:
            otp_model = OTPModel.objects.get(id=otp_id)
            return self._to_domain_entity(otp_model)
        except OTPModel.DoesNotExist:
            return None

    def get_by_code(
        self, code: str, email: Optional[str] = None, phone_number: Optional[str] = None
    ) -> Optional[OTPEntity]:
        """Get OTP by code and identifier."""
        query = Q(otp_code=code, verified=False)
        if email:
            query &= Q(email=email)
        if phone_number:
            query &= Q(phone_number=phone_number)

        try:
            otp_model = OTPModel.objects.filter(query).order_by("-created_at").first()
            if otp_model:
                return self._to_domain_entity(otp_model)
            return None
        except OTPModel.DoesNotExist:
            return None

    def get_latest_by_email(
        self, email: str, purpose: str, otp_type: str
    ) -> Optional[OTPEntity]:
        """Get latest OTP by email, purpose, and type."""
        try:
            otp_model = (
                OTPModel.objects.filter(
                    email=email, purpose=purpose, otp_type=otp_type, verified=False
                )
                .order_by("-created_at")
                .first()
            )
            if otp_model:
                return self._to_domain_entity(otp_model)
            return None
        except OTPModel.DoesNotExist:
            return None

    def get_latest_by_phone(
        self, phone_number: str, purpose: str, otp_type: str
    ) -> Optional[OTPEntity]:
        """Get latest OTP by phone number, purpose, and type."""
        try:
            otp_model = (
                OTPModel.objects.filter(
                    phone_number=phone_number,
                    purpose=purpose,
                    otp_type=otp_type,
                    verified=False,
                )
                .order_by("-created_at")
                .first()
            )
            if otp_model:
                return self._to_domain_entity(otp_model)
            return None
        except OTPModel.DoesNotExist:
            return None

    def update(self, otp: OTPEntity) -> OTPEntity:
        """Update an existing OTP."""
        otp_model = OTPModel.objects.get(id=otp.id)
        otp_model.verified = otp.verified
        otp_model.verified_at = otp.verified_at
        otp_model.attempts = otp.attempts
        otp_model.updated_at = timezone.now()
        otp_model.save()
        return self._to_domain_entity(otp_model)

    def delete(self, otp_id: UUID) -> None:
        """Delete an OTP."""
        OTPModel.objects.filter(id=otp_id).delete()

    def delete_expired(self) -> int:
        """Delete expired OTPs. Returns count of deleted OTPs."""
        queryset = OTPModel.objects.filter(expires_at__lt=timezone.now())
        count = queryset.count()
        queryset.delete()
        return count

    def invalidate_all_pending(
        self,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
        purpose: Optional[str] = None,
        otp_type: Optional[str] = None,
    ) -> int:
        """Invalidate all pending (non-verified) OTPs for given criteria."""
        query = Q(verified=False)
        
        if email:
            query &= Q(email=email)
        if phone_number:
            query &= Q(phone_number=phone_number)
        if purpose:
            query &= Q(purpose=purpose)
        if otp_type:
            query &= Q(otp_type=otp_type)
        
        count = OTPModel.objects.filter(query).update(
            verified=True,
            verified_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return int(count)

    def _to_domain_entity(self, model: OTPModel) -> OTPEntity:
        """Convert Django model to domain entity."""
        return OTPEntity(
            id=model.id,
            user_id=model.user_id if model.user else None,
            email=model.email,
            phone_number=model.phone_number,
            otp_code=model.otp_code,
            otp_type=model.otp_type,
            purpose=model.purpose,
            expires_at=model.expires_at,
            verified=model.verified,
            verified_at=model.verified_at,
            attempts=model.attempts,
            max_attempts=model.max_attempts,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

