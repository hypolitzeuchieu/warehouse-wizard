"""Management app configuration."""

from django.apps import AppConfig


class ManagementConfig(AppConfig):
    """Management commands app configuration."""

    name = "management"
    verbose_name = "Management Commands"

    def ready(self):
        """Register management commands when app is ready."""
        # Commands are automatically discovered by Django
        pass
