"""Django app configuration for persistence models."""

from django.apps import AppConfig


class PersistenceModelsConfig(AppConfig):
    """App config for persistence models."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "infrastructure.persistence.models"
    label = "persistence_models"
    verbose_name = "Persistence Models"

    def ready(self):
        """Import models when app is ready."""
        # Import all models to ensure they're registered with Django
        from infrastructure.persistence.models import (  # noqa: F401
            business_models,
            customer_models,
            delivery_models,
            finance_models,
            inventory_models,
            notification_models,
            sales_models,
            user_models,
        )
