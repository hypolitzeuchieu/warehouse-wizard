from __future__ import annotations

from apps.authentication.models import User
from django.core.exceptions import ValidationError


class UserService:

    @staticmethod
    def manager_role(manager):
        if manager.role != 'manager':
            raise ValidationError('Only managers can manage users.')

    @staticmethod
    def create_users(manager, username, password, role, **extra_fields):
        """
        Allows a manager to create a new user.
        :param manager: The manager creating the user.
        :param username: The username for the new user.
        :param password: The password for the new user.
        :param role: The role of the new user.
        :param extra_fields: Additional fields for the user (e.g., email, phone_number).
        :return: The created user.
        """
        UserService.manager_role(manager)

        user = User.objects.create_user(
            username=username,
            password=password,
            role=role,
            **extra_fields
        )
        return user

    @staticmethod
    def update_user(manager, user_id, **update_fields):
        """
        Allows a manager to update a user.
        :param manager: The manager updating the user.
        :param user_id: The ID of the user to update.
        :param update_fields: Fields to update (e.g., role, email, phone_number).
        :return: The updated user.
        """
        UserService.manager_role(manager)

        user = User.objects.get(id=user_id)
        for field, value in update_fields.items():
            setattr(user, field, value)
        user.save()
        return user

    @staticmethod
    def delete_user(manager, user_id):
        """
        Allows a manager to delete a user.
        :param manager: The manager deleting the user.
        :param user_id: The ID of the user to delete.
        """
        UserService.manager_role(manager)

        user = User.objects.get(id=user_id)
        user.delete()

    @staticmethod
    def assign_role(manager, user_id, role):
        """
        Allows a manager to assign a role to a user.
        :param manager: The manager assigning the role.
        :param user_id: The ID of the user to assign the role to.
        :param role: The role to assign.
        """
        UserService.manager_role(manager)

        user = User.objects.get(id=user_id)
        user.role = role
        user.save()
