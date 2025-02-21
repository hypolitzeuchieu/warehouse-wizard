from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.db import models


class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ROLE_CHOICES = [
        ('manager', 'Manager'),
        ('cashier', 'Cashier'),
        ('stock_keeper', 'Stock Keeper'),
        ('wholesale_client', 'Wholesale Client'),
        ('sales_agent', 'Sales Agent'),
    ]
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    phone_number = models.CharField(max_length=30, null=True, blank=True)
    is_active = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        Group,
        related_name='custom_user_groups',
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='custom_user_permissions',
        blank=True,
    )

    def is_manager(self):
        return self.role == 'manager'

    def is_cashier(self):
        return self.role == 'cashier'

    def is_stock_keeper(self):
        return self.role == 'stock_keeper'

    def is_wholesale_client(self):
        return self.role == 'wholesale_client'
