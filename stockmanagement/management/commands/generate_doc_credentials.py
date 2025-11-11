"""Management command to generate credentials for Swagger/ReDoc access."""

import secrets
import string

from django.core.management.base import BaseCommand
from django.core.management.utils import get_random_secret_key


class Command(BaseCommand):
    """Generate username and password for documentation access."""

    help = "Generate username and password for Swagger/ReDoc authentication"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--username",
            type=str,
            help="Custom username (if not provided, will be generated)",
        )
        parser.add_argument(
            "--password",
            type=str,
            help="Custom password (if not provided, will be generated)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        username = options.get("username")
        password = options.get("password")

        if not username:
            # Generate a random username
            username = f"doc_{secrets.token_urlsafe(8)}"

        if not password:
            # Generate a secure random password
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            password = "".join(secrets.choice(alphabet) for _ in range(16))

        self.stdout.write(
            self.style.SUCCESS("\n" + "=" * 60)
        )
        self.stdout.write(
            self.style.SUCCESS("Documentation Access Credentials Generated")
        )
        self.stdout.write(
            self.style.SUCCESS("=" * 60)
        )
        self.stdout.write(f"\nUsername: {self.style.WARNING(username)}")
        self.stdout.write(f"Password: {self.style.WARNING(password)}")
        self.stdout.write(
            self.style.SUCCESS("\n" + "=" * 60)
        )
        self.stdout.write(
            self.style.WARNING(
                "\nAdd these to your .env file:\n"
                f"DOC_USERNAME={username}\n"
                f"DOC_PASSWORD={password}\n"
            )
        )
        self.stdout.write(
            self.style.SUCCESS("=" * 60 + "\n")
        )

