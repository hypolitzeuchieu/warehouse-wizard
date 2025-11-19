"""Pytest configuration for RetailPulse tests."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "retailpulse.settings")
django.setup()
