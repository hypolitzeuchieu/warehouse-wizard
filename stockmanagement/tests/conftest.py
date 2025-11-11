"""Pytest configuration for RetailPulse tests."""

import os
import django
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stockmanagement.settings")
django.setup()

