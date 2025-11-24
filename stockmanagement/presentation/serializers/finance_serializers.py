"""Finance serializers."""

from decimal import Decimal

from rest_framework import serializers

from application.dto.finance_dto import (
    ExpenseCreateDTO,
    ExpenseResponseDTO,
    ExpenseUpdateDTO,
    PayrollCreateDTO,
    PayrollResponseDTO,
    SalaryCreateDTO,
    SalaryPromotionDTO,
    SalaryResponseDTO,
    SalaryUpdateDTO,
)


class ExpenseListQuerySerializer(serializers.Serializer):
    """Serializer for expense list query parameters."""

    business_id = serializers.UUIDField(required=True)
    expense_type = serializers.ChoiceField(
        choices=[
            "REPLENISHMENT",
            "MISCELLANEOUS",
            "ELECTRICITY",
            "WATER",
            "SALARY",
            "EXTRA",
            "MAINTENANCE",
            "TAX",
            "RENT",
            "MARKETING",
            "INSURANCE",
            "TRANSPORT",
            "UTILITIES",
            "OFFICE_SUPPLIES",
            "PROFESSIONAL_SERVICES",
        ],
        required=False,
        allow_null=True,
    )
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    search = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=1000, default=20)
    order_by = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ExpenseCreateSerializer(serializers.Serializer):
    """Serializer for expense creation."""

    expense_type = serializers.ChoiceField(
        choices=[
            "REPLENISHMENT",
            "MISCELLANEOUS",
            "ELECTRICITY",
            "WATER",
            "SALARY",
            "EXTRA",
            "MAINTENANCE",
            "TAX",
            "RENT",
            "MARKETING",
            "INSURANCE",
            "TRANSPORT",
            "UTILITIES",
            "OFFICE_SUPPLIES",
            "PROFESSIONAL_SERVICES",
        ],
        required=True,
    )
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    reason = serializers.CharField(required=True)

    def to_dto(self) -> ExpenseCreateDTO:
        """Convert to DTO."""
        return ExpenseCreateDTO(
            expense_type=self.validated_data["expense_type"],
            amount=self.validated_data["amount"],
            reason=self.validated_data["reason"],
        )


class ExpenseUpdateSerializer(serializers.Serializer):
    """Serializer for expense update."""

    expense_type = serializers.ChoiceField(
        choices=[
            "REPLENISHMENT",
            "MISCELLANEOUS",
            "ELECTRICITY",
            "WATER",
            "SALARY",
            "EXTRA",
            "MAINTENANCE",
            "TAX",
            "RENT",
            "MARKETING",
            "INSURANCE",
            "TRANSPORT",
            "UTILITIES",
            "OFFICE_SUPPLIES",
            "PROFESSIONAL_SERVICES",
        ],
        required=False,
    )
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, min_value=Decimal("0.01")
    )
    reason = serializers.CharField(required=False)
    is_approved = serializers.BooleanField(required=False)

    def to_dto(self) -> ExpenseUpdateDTO:
        """Convert to DTO."""
        return ExpenseUpdateDTO(
            expense_type=self.validated_data.get("expense_type"),
            amount=self.validated_data.get("amount"),
            reason=self.validated_data.get("reason"),
            is_approved=self.validated_data.get("is_approved"),
        )


class SalaryCreateSerializer(serializers.Serializer):
    """Serializer for salary creation."""

    user_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    currency = serializers.CharField(max_length=10, default="USD", required=False)
    payment_frequency = serializers.ChoiceField(
        choices=["daily", "weekly", "monthly"], default="monthly", required=False
    )
    deductions = serializers.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, required=False
    )
    bonuses = serializers.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, required=False
    )
    effective_from = serializers.DateTimeField(required=False)

    def to_dto(self) -> SalaryCreateDTO:
        """Convert to DTO."""
        from application.dto.finance_dto import SalaryCreateDTO

        return SalaryCreateDTO(
            user_id=self.validated_data["user_id"],
            amount=self.validated_data["amount"],
            currency=self.validated_data.get("currency", "USD"),
            payment_frequency=self.validated_data.get("payment_frequency", "monthly"),
            deductions=self.validated_data.get("deductions", 0.00),
            bonuses=self.validated_data.get("bonuses", 0.00),
            effective_from=self.validated_data.get("effective_from"),
        )


class SalaryUpdateSerializer(serializers.Serializer):
    """Serializer for salary update."""

    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, min_value=Decimal("0.01")
    )
    currency = serializers.CharField(max_length=10, required=False)
    payment_frequency = serializers.ChoiceField(
        choices=["daily", "weekly", "monthly"], required=False
    )
    deductions = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    bonuses = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    effective_from = serializers.DateTimeField(required=False)
    effective_to = serializers.DateTimeField(required=False)

    def to_dto(self) -> SalaryUpdateDTO:
        """Convert to DTO."""
        return SalaryUpdateDTO(
            amount=self.validated_data.get("amount"),
            currency=self.validated_data.get("currency"),
            payment_frequency=self.validated_data.get("payment_frequency"),
            deductions=self.validated_data.get("deductions"),
            bonuses=self.validated_data.get("bonuses"),
            effective_from=self.validated_data.get("effective_from"),
            effective_to=self.validated_data.get("effective_to"),
        )


class SalaryPromotionSerializer(serializers.Serializer):
    """Serializer for employee promotion."""

    new_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    currency = serializers.CharField(max_length=10, default="USD", required=False)
    payment_frequency = serializers.ChoiceField(
        choices=["daily", "weekly", "monthly"], default="monthly", required=False
    )
    deductions = serializers.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, required=False
    )
    bonuses = serializers.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, required=False
    )
    effective_from = serializers.DateTimeField(required=False)
    reason = serializers.CharField(required=False, allow_blank=True)

    def to_dto(self) -> SalaryPromotionDTO:
        """Convert to DTO."""
        return SalaryPromotionDTO(
            new_amount=self.validated_data["new_amount"],
            currency=self.validated_data.get("currency", "USD"),
            payment_frequency=self.validated_data.get("payment_frequency", "monthly"),
            deductions=self.validated_data.get("deductions", 0.00),
            bonuses=self.validated_data.get("bonuses", 0.00),
            effective_from=self.validated_data.get("effective_from"),
            reason=self.validated_data.get("reason"),
        )


class PayrollCreateSerializer(serializers.Serializer):
    """Serializer for payroll creation."""

    user_id = serializers.UUIDField(required=True)
    salary_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    payment_date = serializers.DateTimeField(required=False)
    period_start = serializers.DateTimeField(required=False)
    period_end = serializers.DateTimeField(required=False)
    deductions = serializers.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, required=False
    )
    bonuses = serializers.DecimalField(
        max_digits=15, decimal_places=2, default=0.00, required=False
    )

    def to_dto(self) -> PayrollCreateDTO:
        """Convert to DTO."""
        return PayrollCreateDTO(
            user_id=self.validated_data["user_id"],
            salary_id=self.validated_data["salary_id"],
            amount=self.validated_data["amount"],
            payment_date=self.validated_data.get("payment_date"),
            period_start=self.validated_data.get("period_start"),
            period_end=self.validated_data.get("period_end"),
            deductions=self.validated_data.get("deductions", 0.00),
            bonuses=self.validated_data.get("bonuses", 0.00),
        )


class ExpenseResponseSerializer(serializers.Serializer):
    """Serializer for expense responses."""

    id = serializers.UUIDField()
    business_id = serializers.UUIDField()
    expense_type = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    reason = serializers.CharField()
    user_id = serializers.UUIDField()
    approved_by = serializers.UUIDField(allow_null=True, required=False)
    is_approved = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @classmethod
    def from_dto(cls, dto: ExpenseResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "business_id": dto.business_id,
                "expense_type": dto.expense_type,
                "amount": dto.amount,
                "reason": dto.reason,
                "user_id": dto.user_id,
                "approved_by": dto.approved_by,
                "is_approved": dto.is_approved,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class SalaryResponseSerializer(serializers.Serializer):
    """Serializer for salary responses."""

    id = serializers.UUIDField()
    business_id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    currency = serializers.CharField()
    payment_frequency = serializers.CharField()
    deductions = serializers.DecimalField(max_digits=15, decimal_places=2)
    bonuses = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_salary = serializers.DecimalField(max_digits=15, decimal_places=2)
    effective_from = serializers.DateTimeField()
    effective_to = serializers.DateTimeField(allow_null=True, required=False)
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @classmethod
    def from_dto(cls, dto: SalaryResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "business_id": dto.business_id,
                "user_id": dto.user_id,
                "amount": dto.amount,
                "currency": dto.currency,
                "payment_frequency": dto.payment_frequency,
                "deductions": dto.deductions,
                "bonuses": dto.bonuses,
                "net_salary": dto.net_salary,
                "effective_from": dto.effective_from,
                "effective_to": dto.effective_to,
                "is_active": dto.is_active,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class PayrollResponseSerializer(serializers.Serializer):
    """Serializer for payroll responses."""

    id = serializers.UUIDField()
    business_id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    salary_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    payment_date = serializers.DateTimeField()
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    deductions = serializers.DecimalField(max_digits=15, decimal_places=2)
    bonuses = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @classmethod
    def from_dto(cls, dto: PayrollResponseDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "business_id": dto.business_id,
                "user_id": dto.user_id,
                "salary_id": dto.salary_id,
                "amount": dto.amount,
                "payment_date": dto.payment_date,
                "period_start": dto.period_start,
                "period_end": dto.period_end,
                "deductions": dto.deductions,
                "bonuses": dto.bonuses,
                "net_amount": dto.net_amount,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data
