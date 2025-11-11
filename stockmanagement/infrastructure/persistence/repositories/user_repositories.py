"""User repository implementations."""

from typing import Optional
from uuid import UUID

from django.utils import timezone

from domain.users.entities import AuthMethod, Device, RefreshToken, Session, User, UserRole
from domain.users.repositories import (
    DeviceRepository,
    RefreshTokenRepository,
    SessionRepository,
    UserRepository,
)
from infrastructure.persistence.models.user_models import (
    Device as DeviceModel,
    RefreshToken as RefreshTokenModel,
    RetailPulseUser as UserModel,
    Session as SessionModel,
)


class UserRepositoryImpl(UserRepository):
    """Django implementation of UserRepository."""

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        try:
            user_model = UserModel.objects.get(id=user_id)
            return self._to_entity(user_model)
        except UserModel.DoesNotExist:
            return None

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        try:
            user_model = UserModel.objects.get(email=email)
            return self._to_entity(user_model)
        except UserModel.DoesNotExist:
            return None

    def get_by_phone_number(self, phone_number: str) -> Optional[User]:
        """Get user by phone number."""
        try:
            user_model = UserModel.objects.get(phone_number=phone_number)
            return self._to_entity(user_model)
        except UserModel.DoesNotExist:
            return None

    def create(self, user: User, password: Optional[str] = None) -> User:
        """Create a new user."""
        user_model = UserModel(
            id=user.id,
            email=user.email,
            name=user.name,
            phone_number=user.phone_number,
            role=user.role.value if isinstance(user.role, UserRole) else user.role,
            is_active=user.is_active,
            is_staff=user.is_staff,
            is_superuser=user.is_superuser,
            last_login=user.last_login,
            address=user.address,
            avatar_url=user.avatar_url,
            auth_method=user.auth_method.value if isinstance(user.auth_method, AuthMethod) else user.auth_method,
        )
        if password:
            user_model.set_password(password)
        else:
            user_model.set_unusable_password()
        user_model.save()
        return self._to_entity(user_model)

    def update(self, user: User) -> User:
        """Update an existing user."""
        user_model = UserModel.objects.get(id=user.id)
        user_model.email = user.email
        user_model.name = user.name
        user_model.phone_number = user.phone_number
        user_model.role = user.role.value if isinstance(user.role, UserRole) else user.role
        user_model.is_active = user.is_active
        user_model.is_staff = user.is_staff
        user_model.is_superuser = user.is_superuser
        user_model.last_login = user.last_login
        user_model.address = user.address
        user_model.avatar_url = user.avatar_url
        user_model.auth_method = user.auth_method.value if isinstance(user.auth_method, AuthMethod) else user.auth_method
        user_model.save()
        return self._to_entity(user_model)

    def delete(self, user_id: UUID) -> None:
        """Delete a user."""
        UserModel.objects.filter(id=user_id).delete()

    def get_by_role(self, role: UserRole) -> list[User]:
        """Get users by role."""
        users = UserModel.objects.filter(role=role.value)
        return [self._to_entity(user) for user in users]

    def verify_password(self, user_id: UUID, password: str) -> bool:
        """Verify user password."""
        try:
            user_model = UserModel.objects.get(id=user_id)
            password_valid = user_model.check_password(password)
            return bool(password_valid)
        except UserModel.DoesNotExist:
            return False

    def _to_entity(self, user_model: UserModel) -> User:
        """Convert Django model to domain entity."""
        return User(
            id=user_model.id,
            email=user_model.email or "",
            name=user_model.name or (user_model.email.split("@")[0] if user_model.email else "User"),
            phone_number=user_model.phone_number,
            role=UserRole(user_model.role),
            is_active=user_model.is_active,
            is_staff=user_model.is_staff,
            is_superuser=user_model.is_superuser,
            created_at=user_model.created_at,
            updated_at=user_model.updated_at,
            last_login=user_model.last_login,
            address=user_model.address,
            avatar_url=user_model.avatar_url,
            auth_method=AuthMethod(user_model.auth_method) if user_model.auth_method else AuthMethod.EMAIL_PASSWORD,
        )


class SessionRepositoryImpl(SessionRepository):
    """Django implementation of SessionRepository."""

    def get_by_id(self, session_id: UUID) -> Optional[Session]:
        """Get session by ID."""
        try:
            session_model = SessionModel.objects.get(id=session_id)
            return self._to_entity(session_model)
        except SessionModel.DoesNotExist:
            return None

    def get_active_sessions_by_user(self, user_id: UUID) -> list[Session]:
        """Get active sessions for a user."""
        sessions = SessionModel.objects.filter(
            user_id=user_id, end_time__isnull=True
        )
        return [self._to_entity(session) for session in sessions]

    def create(self, session: Session) -> Session:
        """Create a new session."""
        session_model = SessionModel(
            id=session.id,
            user_id=session.user_id,
            device_id=session.device_id,
            start_time=session.start_time,
            end_time=session.end_time,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
        )
        session_model.save()
        return self._to_entity(session_model)

    def update(self, session: Session) -> Session:
        """Update an existing session."""
        session_model = SessionModel.objects.get(id=session.id)
        session_model.end_time = session.end_time
        session_model.save()
        return self._to_entity(session_model)

    def get_user_sessions(
        self, user_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Session]:
        """Get user session history."""
        sessions = SessionModel.objects.filter(user_id=user_id).order_by(
            "-start_time"
        )[offset : offset + limit]
        return [self._to_entity(session) for session in sessions]

    def get_user_sessions_with_devices(
        self, user_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[tuple[Session, Optional[Device]]]:
        """
        Get user session history with device information.
        
        Returns:
            List of tuples (Session, Device or None)
        """
        sessions = SessionModel.objects.filter(user_id=user_id).order_by(
            "-start_time"
        )[offset:offset + limit]

        # Get all device_ids from sessions
        device_ids = [s.device_id for s in sessions if s.device_id]
        # Fetch devices in bulk
        devices_dict = {}
        if device_ids:
            devices = DeviceModel.objects.filter(
                device_id__in=device_ids, user_id=user_id
            )
            devices_dict = {d.device_id: d for d in devices}

        # Convert to entities and pair with devices
        result = []
        for session in sessions:
            session_entity = self._to_entity(session)
            device_model = (
                devices_dict.get(session.device_id) if session.device_id else None
            )
            device_entity = None
            if device_model:
                device_entity = Device(
                    id=device_model.id,
                    user_id=device_model.user_id,
                    device_id=device_model.device_id,
                    device_name=device_model.device_name,
                    device_type=device_model.device_type,
                    ip_address=device_model.ip_address,
                    user_agent=device_model.user_agent,
                    last_used_at=device_model.last_used_at,
                    created_at=device_model.created_at,
                    updated_at=device_model.updated_at,
                )
            result.append((session_entity, device_entity))

        return result

    def _to_entity(self, session_model: SessionModel) -> Session:
        """Convert Django model to domain entity."""
        return Session(
            id=session_model.id,
            user_id=session_model.user_id,
            device_id=session_model.device_id,
            start_time=session_model.start_time,
            end_time=session_model.end_time,
            ip_address=session_model.ip_address,
            user_agent=session_model.user_agent,
            created_at=session_model.created_at,
            updated_at=session_model.updated_at,
        )


class RefreshTokenRepositoryImpl(RefreshTokenRepository):
    """Django implementation of RefreshTokenRepository."""

    def get_by_id(self, token_id: UUID) -> Optional[RefreshToken]:
        """Get refresh token by ID."""
        try:
            token_model = RefreshTokenModel.objects.get(id=token_id)
            return self._to_entity(token_model)
        except RefreshTokenModel.DoesNotExist:
            return None

    def get_by_token(self, token: str) -> Optional[RefreshToken]:
        """Get refresh token by token string."""
        try:
            token_model = RefreshTokenModel.objects.get(token=token)
            return self._to_entity(token_model)
        except RefreshTokenModel.DoesNotExist:
            return None

    def get_by_user_and_device(
        self, user_id: UUID, device_id: Optional[str]
    ) -> list[RefreshToken]:
        """Get refresh tokens for a user and device."""
        query = RefreshTokenModel.objects.filter(user_id=user_id)
        if device_id:
            query = query.filter(device_id=device_id)
        tokens = query.filter(revoked=False)
        return [self._to_entity(token) for token in tokens]

    def create(self, refresh_token: RefreshToken) -> RefreshToken:
        """Create a new refresh token."""
        token_model = RefreshTokenModel(
            id=refresh_token.id,
            user_id=refresh_token.user_id,
            token=refresh_token.token,
            device_id=refresh_token.device_id,
            ip_address=refresh_token.ip_address,
            expires_at=refresh_token.expires_at,
            revoked=refresh_token.revoked,
            revoked_at=refresh_token.revoked_at,
        )
        token_model.save()
        return self._to_entity(token_model)

    def update(self, refresh_token: RefreshToken) -> RefreshToken:
        """Update an existing refresh token."""
        token_model = RefreshTokenModel.objects.get(id=refresh_token.id)
        token_model.revoked = refresh_token.revoked
        token_model.revoked_at = refresh_token.revoked_at
        token_model.expires_at = refresh_token.expires_at
        token_model.device_id = refresh_token.device_id
        token_model.ip_address = refresh_token.ip_address
        token_model.save()
        return self._to_entity(token_model)

    def revoke(self, token_id: UUID) -> None:
        """Revoke a refresh token."""
        RefreshTokenModel.objects.filter(id=token_id).update(
            revoked=True, revoked_at=timezone.now()
        )

    def revoke_all_user_tokens(self, user_id: UUID) -> None:
        """Revoke all refresh tokens for a user."""
        RefreshTokenModel.objects.filter(user_id=user_id, revoked=False).update(
            revoked=True, revoked_at=timezone.now()
        )

    def revoke_user_device_tokens(self, user_id: UUID, device_id: str) -> None:
        """Revoke refresh tokens for a specific user device."""
        RefreshTokenModel.objects.filter(
            user_id=user_id, device_id=device_id, revoked=False
        ).update(revoked=True, revoked_at=timezone.now())

    def _to_entity(self, token_model: RefreshTokenModel) -> RefreshToken:
        """Convert Django model to domain entity."""
        return RefreshToken(
            id=token_model.id,
            user_id=token_model.user_id,
            token=token_model.token,
            device_id=token_model.device_id,
            ip_address=token_model.ip_address,
            expires_at=token_model.expires_at,
            revoked=token_model.revoked,
            revoked_at=token_model.revoked_at,
            created_at=token_model.created_at,
            updated_at=token_model.updated_at,
        )


class DeviceRepositoryImpl(DeviceRepository):
    """Django implementation of DeviceRepository."""

    def get_by_id(self, device_id: UUID) -> Optional[Device]:
        """Get device by ID."""
        try:
            device_model = DeviceModel.objects.get(id=device_id)
            return self._to_entity(device_model)
        except DeviceModel.DoesNotExist:
            return None

    def get_by_device_id(self, device_id: str) -> Optional[Device]:
        """Get device by device ID string."""
        try:
            device_model = DeviceModel.objects.get(device_id=device_id)
            return self._to_entity(device_model)
        except DeviceModel.DoesNotExist:
            return None

    def get_user_devices(self, user_id: UUID) -> list[Device]:
        """Get all devices for a user."""
        devices = DeviceModel.objects.filter(user_id=user_id, is_active=True)
        return [self._to_entity(device) for device in devices]

    def create(self, device: Device) -> Device:
        """Create a new device."""
        device_model = DeviceModel(
            id=device.id,
            user_id=device.user_id,
            device_id=device.device_id,
            device_name=device.device_name,
            device_type=device.device_type,
            ip_address=device.ip_address,
            user_agent=device.user_agent,
            is_active=True,  # Default to active when creating
        )
        device_model.save()
        return self._to_entity(device_model)

    def update(self, device: Device) -> Device:
        """Update an existing device."""
        device_model = DeviceModel.objects.get(id=device.id)
        device_model.device_name = device.device_name
        device_model.device_type = device.device_type
        device_model.ip_address = device.ip_address
        device_model.user_agent = device.user_agent
        # Note: is_active is managed by the model, not the entity
        device_model.save()
        return self._to_entity(device_model)

    def delete(self, device_id: UUID) -> None:
        """Delete a device."""
        DeviceModel.objects.filter(id=device_id).delete()

    def _to_entity(self, device_model: DeviceModel) -> Device:
        """Convert Django model to domain entity."""
        return Device(
            id=device_model.id,
            user_id=device_model.user_id,
            device_id=device_model.device_id,
            device_name=device_model.device_name,
            device_type=device_model.device_type,
            ip_address=device_model.ip_address,
            user_agent=device_model.user_agent,
            last_used_at=device_model.last_used_at,
            created_at=device_model.created_at,
            updated_at=device_model.updated_at,
        )

