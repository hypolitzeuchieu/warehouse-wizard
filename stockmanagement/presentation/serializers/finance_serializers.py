"""Finance serializers."""

from decimal import Decimal

from rest_framework import serializers

from application.dto.finance_dto import (
    ExpenseAuditLogDTO,
    ExpenseCreateDTO,
    ExpenseResponseDTO,
    ExpenseSummaryDTO,
    ExpenseUpdateDTO,
    PayrollCreateDTO,
    PayrollResponseDTO,
    SalaryCreateDTO,
    SalaryPromotionDTO,
    SalaryResponseDTO,
    SalaryUpdateDTO,
)

PAYMENT_METHOD_CHOICES = [
    "CASH",
    "MOBILE_MONEY",
    "BANK_TRANSFER",
    "CARD",
    "CHECK",
    "OTHER",
]

PAYEE_TYPE_CHOICES = [
    "EMPLOYEE",
    "SUPPLIER",
    "SERVICE_PROVIDER",
    "GOVERNMENT",
    "LANDLORD",
    "OTHER",
]


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
    payment_method = serializers.ChoiceField(
        choices=PAYMENT_METHOD_CHOICES, required=False, allow_null=True
    )
    payee_type = serializers.ChoiceField(
        choices=PAYEE_TYPE_CHOICES, required=False, allow_null=True
    )
    min_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0.00")
    )
    max_amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0.00")
    )
    is_approved = serializers.BooleanField(required=False)


class ExpenseCreateSerializer(serializers.Serializer):
    """Serializer for expense creation."""

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
        required=True,
    )
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    reason = serializers.CharField(required=True)
    reason_details = serializers.CharField(required=True)
    payee_name = serializers.CharField(required=True)
    payee_type = serializers.ChoiceField(choices=PAYEE_TYPE_CHOICES, required=True)
    payment_method = serializers.ChoiceField(choices=PAYMENT_METHOD_CHOICES, required=True)
    payment_reference = serializers.CharField(required=False, allow_blank=True)
    justification_metadata = serializers.JSONField(required=False)

    def validate(self, attrs):
        justification = attrs.get("justification_metadata") or {}
        if (
            attrs["expense_type"] == "SALARY"
            and "salary_id" not in justification
            and "employee_id" not in justification
        ):
            raise serializers.ValidationError(
                "salary expenses require salary_id or employee_id in justification_metadata"
            )
        return attrs

    def to_dto(self) -> ExpenseCreateDTO:
        """Convert to DTO."""
        return ExpenseCreateDTO(
            expense_type=self.validated_data["expense_type"],
            amount=self.validated_data["amount"],
            reason=self.validated_data["reason"],
            reason_details=self.validated_data["reason_details"],
            payment_method=self.validated_data["payment_method"],
            payment_reference=self.validated_data.get("payment_reference"),
            payee_type=self.validated_data["payee_type"],
            payee_name=self.validated_data["payee_name"],
            justification_metadata=self.validated_data.get("justification_metadata", {}),
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
    reason_details = serializers.CharField(required=False)
    is_approved = serializers.BooleanField(required=False)
    payee_name = serializers.CharField(required=False)
    payee_type = serializers.ChoiceField(choices=PAYEE_TYPE_CHOICES, required=False)
    payment_method = serializers.ChoiceField(choices=PAYMENT_METHOD_CHOICES, required=False)
    payment_reference = serializers.CharField(required=False, allow_blank=True)
    justification_metadata = serializers.JSONField(required=False)

    def to_dto(self) -> ExpenseUpdateDTO:
        """Convert to DTO."""
        return ExpenseUpdateDTO(
            expense_type=self.validated_data.get("expense_type"),
            amount=self.validated_data.get("amount"),
            reason=self.validated_data.get("reason"),
            reason_details=self.validated_data.get("reason_details"),
            is_approved=self.validated_data.get("is_approved"),
            payment_method=self.validated_data.get("payment_method"),
            payment_reference=self.validated_data.get("payment_reference"),
            payee_type=self.validated_data.get("payee_type"),
            payee_name=self.validated_data.get("payee_name"),
            justification_metadata=self.validated_data.get("justification_metadata"),
        )


class SalaryCreateSerializer(serializers.Serializer):
    """Serializer for salary creation."""

    user_id = serializers.UUIDField(required=True)
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=True, min_value=Decimal("0.01")
    )
    currency = serializers.CharField(max_length=10, default="Fcfa", required=False)
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
        return SalaryCreateDTO(
            user_id=self.validated_data["user_id"],
            amount=self.validated_data["amount"],
            currency=self.validated_data.get("currency", "Fcfa"),
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
    currency = serializers.CharField(max_length=10, default="Fcfa", required=False)
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
            currency=self.validated_data.get("currency", "Fcfa"),
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
    reason_details = serializers.CharField(allow_blank=True, required=False)
    user_id = serializers.UUIDField()
    user_name = serializers.CharField(allow_blank=True, required=False)
    approved_by = serializers.UUIDField(allow_null=True, required=False)
    is_approved = serializers.BooleanField()
    payment_method = serializers.CharField()
    payment_reference = serializers.CharField(allow_blank=True, required=False)
    payee_type = serializers.CharField()
    payee_name = serializers.CharField(allow_blank=True, required=False)
    justification_metadata = serializers.JSONField()
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
                "reason_details": dto.reason_details,
                "user_id": dto.user_id,
                "user_name": dto.user_name or "",
                "approved_by": dto.approved_by,
                "is_approved": dto.is_approved,
                "payment_method": dto.payment_method,
                "payment_reference": dto.payment_reference,
                "payee_type": dto.payee_type,
                "payee_name": dto.payee_name,
                "justification_metadata": dto.justification_metadata,
                "created_at": dto.created_at,
                "updated_at": dto.updated_at,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class ExpenseHistoryResponseSerializer(serializers.Serializer):
    """Serializer representing expense audit history."""

    id = serializers.UUIDField()
    expense_id = serializers.UUIDField()
    action = serializers.CharField()
    performed_by = serializers.UUIDField(allow_null=True)
    amount_before = serializers.DecimalField(max_digits=15, decimal_places=2, allow_null=True)
    amount_after = serializers.DecimalField(max_digits=15, decimal_places=2, allow_null=True)
    reason_before = serializers.CharField(allow_null=True)
    reason_after = serializers.CharField(allow_null=True)
    reason_details_before = serializers.CharField(allow_null=True)
    reason_details_after = serializers.CharField(allow_null=True)
    payment_method_before = serializers.CharField(allow_null=True)
    payment_method_after = serializers.CharField(allow_null=True)
    payee_type_before = serializers.CharField(allow_null=True)
    payee_type_after = serializers.CharField(allow_null=True)
    payee_name_before = serializers.CharField(allow_null=True)
    payee_name_after = serializers.CharField(allow_null=True)
    justification_snapshot = serializers.JSONField()
    created_at = serializers.DateTimeField()

    @classmethod
    def from_dto(cls, dto: ExpenseAuditLogDTO) -> dict:
        serializer = cls(
            data={
                "id": dto.id,
                "expense_id": dto.expense_id,
                "action": dto.action,
                "performed_by": dto.performed_by,
                "amount_before": dto.amount_before,
                "amount_after": dto.amount_after,
                "reason_before": dto.reason_before,
                "reason_after": dto.reason_after,
                "reason_details_before": dto.reason_details_before,
                "reason_details_after": dto.reason_details_after,
                "payment_method_before": dto.payment_method_before,
                "payment_method_after": dto.payment_method_after,
                "payee_type_before": dto.payee_type_before,
                "payee_type_after": dto.payee_type_after,
                "payee_name_before": dto.payee_name_before,
                "payee_name_after": dto.payee_name_after,
                "justification_snapshot": dto.justification_snapshot,
                "created_at": dto.created_at,
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.data


class ExpenseSummaryQuerySerializer(serializers.Serializer):
    """Serializer for expense summary query params."""

    business_id = serializers.UUIDField(required=True)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)


class ExpenseSummaryResponseSerializer(serializers.Serializer):
    """Serializer for expense summary response."""

    business_id = serializers.UUIDField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_count = serializers.IntegerField()
    by_type = serializers.ListField(child=serializers.DictField())
    by_payment_method = serializers.DictField(
        child=serializers.DecimalField(max_digits=15, decimal_places=2)
    )
    monthly_stats = serializers.ListField(child=serializers.DictField())

    @classmethod
    def from_dto(cls, dto: ExpenseSummaryDTO) -> dict:
        serializer = cls(
            data={
                "business_id": dto.business_id,
                "total_amount": dto.total_amount,
                "total_count": dto.total_count,
                "by_type": [
                    {
                        "expense_type": stat.expense_type,
                        "total_amount": stat.total_amount,
                        "count": stat.count,
                        "average_amount": stat.average_amount,
                        "percentage_of_total": stat.percentage_of_total,
                    }
                    for stat in dto.by_type
                ],
                "by_payment_method": dto.by_payment_method,
                "monthly_stats": [
                    {
                        "month": stat.month.isoformat(),
                        "total_amount": stat.total_amount,
                        "count": stat.count,
                    }
                    for stat in dto.monthly_stats
                ],
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
