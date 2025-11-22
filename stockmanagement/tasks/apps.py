"""Django app configuration for Celery tasks."""

from django.apps import AppConfig


class TasksConfig(AppConfig):
    """App config for Celery tasks."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tasks"
    verbose_name = "Celery Tasks"

    def ready(self):
        """
        Import tasks when app is ready.

        This ensures tasks are registered with Celery after Django is fully initialized.
        """
        try:
            import tasks.inventory_tasks  # noqa: F401
            import tasks.otp_tasks  # noqa: F401
            import tasks.password_reset_tasks  # noqa: F401
            import tasks.send_mail  # noqa: F401
        except ImportError as e:
            # Log but don't fail if tasks can't be imported
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Could not import some tasks: {e}")
