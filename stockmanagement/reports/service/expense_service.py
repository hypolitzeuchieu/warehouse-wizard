from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from reports.models import Expense
from reports.models import Treasure
from reports.service.entities import ServiceResponse

logger = logging.getLogger(__name__)


class ExpenseService:

    @staticmethod
    def create_expense(amount, expense_type, reason, created_by) -> ServiceResponse:
        try:
            with transaction.atomic():
                treasure = TreasureService.get_treasure()
                if treasure.balance < Decimal(amount):
                    return ServiceResponse(
                        success=False,
                        error='Insufficient balance to perform this expense'
                    )

                expense = Expense.objects.create(
                    amount=amount,
                    expense_type=expense_type,
                    reason=reason,
                    created_by=created_by
                )

                TreasureService.update_balance(
                    amount=Decimal(amount),
                    operation_type='expense',
                    details={
                        'expense_id': str(expense.id),
                        'reason': reason
                    }
                )
                logger.info(f'Expense successfully created: {expense}')
                return ServiceResponse(success=True, data=expense)

        except Exception as e:
            logger.error(f"Error creating expense: {str(e)}")
            return ServiceResponse(success=False, error=str(e))

    @staticmethod
    def update_expense(
            expense_id, new_amount, expense_type, reason, updated_by
    ) -> ServiceResponse:
        try:
            with transaction.atomic():
                expense = Expense.objects.select_for_update().get(id=expense_id)
                old_amount = expense.amount
                diff = Decimal(new_amount) - Decimal(old_amount)

                if diff != 0:
                    if diff > 0:
                        TreasureService.update_balance(
                            amount=diff,
                            operation_type='expense',
                            details={
                                'expense_id': str(expense.id),
                                'reason': f"Expense update - increase: {reason}",
                                'old_amount': float(old_amount),
                                'new_amount': float(new_amount)
                            }
                        )
                    else:
                        TreasureService.update_balance(
                            amount=abs(diff),
                            operation_type='expense_adjustment',
                            details={
                                'expense_id': str(expense.id),
                                'reason': f"Expense update - decrease: {reason}",
                                'old_amount': float(old_amount),
                                'new_amount': float(new_amount)
                            }
                        )
                expense.amount = new_amount
                expense.updated_by = updated_by
                expense.expense_type = expense_type
                expense.reason = reason
                expense.save()

                logger.info(f"Expense record updated: {expense}")
                return ServiceResponse(success=True, data=expense)

        except Expense.DoesNotExist:
            logger.error(f"Expense with ID {expense_id} not found.")
            return ServiceResponse(success=False, error='Expense not found')
        except ValueError as ve:
            return ServiceResponse(success=False, error=str(ve))
        except Exception as e:
            logger.error(f"Error updating expense: {str(e)}")
            return ServiceResponse(success=False, error=str(e))


class TreasureService:

    DEFAULT_TREASURE_ID = UUID('00000000-0000-0000-0000-000000000001')

    @staticmethod
    def get_treasure():
        """get or create the default treasure record"""
        treasure, _ = Treasure.objects.select_for_update().get_or_create(
            id=TreasureService.DEFAULT_TREASURE_ID,
            defaults={
                'balance': Decimal('0.00'),
                'total_sales': Decimal('0.00'),
                'total_expenses': Decimal('0.00'),
                'total_credit': Decimal('0.00'),
                'outstanding_debt': Decimal('0.00'),
                'history': []
            }
        )
        return treasure

    @staticmethod
    def update_balance(amount: Decimal, operation_type: str, details: dict = None):
        if details is None:
            details = {}

        with transaction.atomic():
            treasure = TreasureService.get_treasure()

            history_entry = {
                'timestamp': timezone.now().isoformat(),
                'operation': operation_type,
                'amount': float(amount),
                'details': details,
                'previous_balance': float(treasure.balance),
                'previous_expenses': float(treasure.total_expenses),
                'previous_outstanding': float(treasure.outstanding_debt)
            }

            if operation_type == 'expense':
                if amount > treasure.balance:
                    raise ValueError(
                        f"Insufficient balance for expense: {amount} > {treasure.balance}"
                        f" | Détails: {details}"
                    )
                treasure.balance -= amount
                treasure.total_expenses += amount

            elif operation_type == 'expense_revert':
                treasure.balance += amount
                treasure.total_expenses -= amount

            elif operation_type == 'sale':
                treasure.balance += amount
                treasure.total_sales += amount

            elif operation_type == 'credit_sale':
                treasure.total_credit += amount
                treasure.outstanding_debt += amount

            elif operation_type == 'credit_payment':
                treasure.balance += amount
                treasure.outstanding_debt -= amount

            elif operation_type == 'expense_adjustment':
                treasure.balance += amount
                treasure.total_expenses -= amount

            history_entry.update({
                'new_balance': float(treasure.balance),
                'new_expenses': float(treasure.total_expenses),
                'new_outstanding': float(treasure.outstanding_debt)
            })

            treasure.history.append(history_entry)
            if len(treasure.history) > 100:
                treasure.history = treasure.history[-100:]

            treasure.save()
            return treasure
