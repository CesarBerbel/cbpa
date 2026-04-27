from dateutil.relativedelta import relativedelta
from django.db import models
from django.utils import timezone

from finances.models import FinancialMovement
from finances.services.date_service import get_month_start_and_end


def calculate_account_projected_balance_until(account, end_date):
    """
    Calculate projected balance including paid, pending and overdue movements.
    """
    movements = FinancialMovement.objects.filter(
        account=account,
        due_date__lte=end_date,
        status__in=[
            FinancialMovement.MovementStatus.PAID,
            FinancialMovement.MovementStatus.PENDING,
            FinancialMovement.MovementStatus.OVERDUE,
        ],
    )

    balance = account.initial_balance

    for movement in movements:
        balance += movement.signed_amount

    return balance


def calculate_account_real_balance_until(account, end_date):
    """
    Calculate real balance using only paid movements.
    """
    movements = FinancialMovement.objects.filter(
        account=account,
        paid_at__isnull=False,
        paid_at__lte=end_date,
        status=FinancialMovement.MovementStatus.PAID,
    )

    balance = account.initial_balance

    for movement in movements:
        balance += movement.signed_amount

    return balance


def calculate_account_month_summary(account, year, month):
    """
    Calculate initial, current and expected balances for a financial account.
    """
    month_start, month_end = get_month_start_and_end(year, month)

    today = timezone.localdate()
    current_month_start = today.replace(day=1)
    previous_day = month_start - relativedelta(days=1)

    is_past_month = month_start < current_month_start

    if is_past_month:
        initial_balance = calculate_account_real_balance_until(
            account=account,
            end_date=previous_day,
        )
    else:
        initial_balance = calculate_account_projected_balance_until(
            account=account,
            end_date=previous_day,
        )

    paid_movements = FinancialMovement.objects.filter(
        account=account,
        paid_at__isnull=False,
        paid_at__gte=month_start,
        paid_at__lte=month_end,
        status=FinancialMovement.MovementStatus.PAID,
    )

    open_movements = FinancialMovement.objects.filter(
        account=account,
        paid_at__isnull=True,
        due_date__gte=month_start,
        due_date__lte=month_end,
        status__in=[
            FinancialMovement.MovementStatus.PENDING,
            FinancialMovement.MovementStatus.OVERDUE,
        ],
    )

    current_balance = initial_balance

    for movement in paid_movements:
        current_balance += movement.signed_amount

    expected_balance = current_balance

    for movement in open_movements:
        expected_balance += movement.signed_amount

    return {
        "initial_balance": initial_balance,
        "current_balance": current_balance,
        "expected_balance": expected_balance,
    }


def get_movements_for_display_month(company, year, month, account=None):
    """
    Return movements that should appear in the selected month.
    """
    month_start, month_end = get_month_start_and_end(year, month)

    queryset = FinancialMovement.objects.filter(
        company=company,
    )

    if account:
        queryset = queryset.filter(
            account=account,
        )

    return queryset.filter(
        models.Q(
            paid_at__isnull=False,
            paid_at__gte=month_start,
            paid_at__lte=month_end,
        )
        | models.Q(
            paid_at__isnull=True,
            due_date__gte=month_start,
            due_date__lte=month_end,
        )
    ).order_by(
        "-paid_at",
        "-due_date",
        "-id",
    )
