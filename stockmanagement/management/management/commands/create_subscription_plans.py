"""Management command to create initial subscription plans."""

from decimal import Decimal
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.utils import timezone

from domain.subscription.entities import SubscriptionPlan
from infrastructure.persistence.repositories import SubscriptionPlanRepositoryImpl


class Command(BaseCommand):
    """Command to create initial subscription plans."""

    help = "Create initial subscription plans (Basic and Pro)"

    def handle(self, *args, **options):
        """Execute command."""
        repository = SubscriptionPlanRepositoryImpl()

        # Check if plans already exist
        existing_basic = repository.get_by_code("basic")
        existing_pro = repository.get_by_code("pro")

        if existing_basic and existing_pro:
            self.stdout.write(
                self.style.WARNING(
                    "Subscription plans already exist. Skipping creation."
                )
            )
            return

        now = timezone.now()

        # Create Basic plan
        if not existing_basic:
            basic_plan = SubscriptionPlan(
                id=uuid4(),
                name="Basic Plan",
                code="basic",
                description="Basic subscription plan with essential features",
                monthly_price=Decimal("5000.00"),  # 5000 XAF per month
                annual_price=Decimal("50000.00"),  # 50000 XAF per year (2 months free)
                features={
                    # NOTE: Features are stored but not enforced yet.
                    # Restrictions based on these features will be implemented later.
                    "max_users": 5,
                    "max_products": 100,
                    "reports": True,
                    "support": "email",
                },
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            repository.create(basic_plan)
            self.stdout.write(self.style.SUCCESS("✓ Created Basic plan"))

        # Create Pro plan
        if not existing_pro:
            pro_plan = SubscriptionPlan(
                id=uuid4(),
                name="Pro Plan",
                code="pro",
                description="Professional subscription plan with advanced features",
                monthly_price=Decimal("15000.00"),  # 15000 XAF per month
                annual_price=Decimal(
                    "150000.00"
                ),  # 150000 XAF per year (2 months free)
                features={
                    # NOTE: Features are stored but not enforced yet.
                    # Restrictions based on these features will be implemented later.
                    "max_users": 20,
                    "max_products": 1000,
                    "reports": True,
                    "advanced_reports": True,
                    "support": "priority",
                    "api_access": True,
                },
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            repository.create(pro_plan)
            self.stdout.write(self.style.SUCCESS("✓ Created Pro plan"))

        self.stdout.write(
            self.style.SUCCESS("\n✓ Subscription plans created successfully!")
        )
