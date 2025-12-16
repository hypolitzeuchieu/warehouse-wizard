"""Management command to generate credentials for Swagger/ReDoc access."""

from django.core.management.base import BaseCommand

from application.use_cases.doc_credential_use_cases import GenerateDocCredentialUseCase
from infrastructure.persistence.repositories import DocumentationCredentialRepositoryImpl


class Command(BaseCommand):
    """Generate credentials for documentation access."""

    help = "Generate credentials for Swagger/ReDoc authentication. Username will be prompted if not provided, password will be auto-generated."

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "username",
            type=str,
            nargs="?",
            help="Username for documentation access (will be prompted if not provided)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days the credential will be valid (default: 7)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        username = options.get("username")
        days_valid = options.get("days", 7)

        if not username:
            self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
            self.stdout.write(self.style.SUCCESS("Documentation Credentials Generator"))
            self.stdout.write(self.style.SUCCESS("=" * 60 + "\n"))
            username = input(self.style.WARNING("Enter username: ")).strip()

            if not username:
                self.stdout.write(self.style.ERROR("\nError: Username cannot be empty.\n"))
                return

            if days_valid == 7:
                days_input = input(
                    self.style.WARNING("Enter number of days (default: 7): ")
                ).strip()
                if days_input:
                    try:
                        days_valid = int(days_input)
                    except ValueError:
                        self.stdout.write(
                            self.style.ERROR("\nInvalid number of days. Using default: 7\n")
                        )
                        days_valid = 7

        try:
            repository = DocumentationCredentialRepositoryImpl()
            use_case = GenerateDocCredentialUseCase(repository)
            credential, plain_password = use_case.execute(username=username, days_valid=days_valid)

            self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
            self.stdout.write(self.style.SUCCESS("Documentation Access Credentials Generated"))
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(f"\nUsername: {self.style.WARNING(credential.username)}")
            self.stdout.write(f"Password: {self.style.WARNING(plain_password)}")
            self.stdout.write(
                f"\nExpires at: {self.style.WARNING(credential.expires_at.strftime('%Y-%m-%d %H:%M:%S'))}"
            )
            self.stdout.write(f"Credential ID: {self.style.SUCCESS(str(credential.id))}")
            self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  IMPORTANT: Save this password now. It cannot be retrieved later!\n"
                    "The credential has been saved to the database and is active.\n"
                    "Previous active credentials have been deactivated.\n"
                    "To manage credentials (delete, activate, deactivate), use the Django admin panel."
                )
            )
            self.stdout.write(self.style.SUCCESS("=" * 60 + "\n"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nError generating credentials: {str(e)}\n"))
            raise
