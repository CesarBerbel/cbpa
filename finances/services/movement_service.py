import uuid
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from finances.models import FinancialMovement


def get_manual_movement_initial_status(due_date):
    """
    Return initial status for manually created movements.
    """
    if due_date < timezone.localdate():
        return FinancialMovement.MovementStatus.OVERDUE

    return FinancialMovement.MovementStatus.PENDING


@transaction.atomic
def create_single_movement(
    company,
    account,
    movement_type,
    amount,
    due_date,
    description="",
    category=None,
    subcategory=None,
):
    """
    Create a single financial movement.
    """
    return FinancialMovement.objects.create(
        company=company,
        account=account,
        movement_type=movement_type,
        category=category,
        subcategory=subcategory,
        recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
        description=description,
        amount=amount,
        due_date=due_date,
        status=get_manual_movement_initial_status(due_date),
    )


@transaction.atomic
def create_installment_movements(
    company,
    account,
    movement_type,
    amount,
    due_date,
    installments,
    amount_mode,
    description="",
    category=None,
    subcategory=None,
):
    """
    Create installment financial movements.
    """
    group = str(uuid.uuid4())

    if amount_mode == "TOTAL":
        installment_amount = amount / Decimal(installments)
    else:
        installment_amount = amount

    movements = []

    for index in range(installments):
        installment_due_date = due_date + relativedelta(months=index)

        movement = FinancialMovement.objects.create(
            company=company,
            account=account,
            movement_type=movement_type,
            category=category,
            subcategory=subcategory,
            recurrence_type=FinancialMovement.RecurrenceType.INSTALLMENT,
            description=description,
            amount=installment_amount,
            due_date=installment_due_date,
            status=get_manual_movement_initial_status(installment_due_date),
            installment_group=group,
            installment_number=index + 1,
            installment_total=installments,
        )

        movements.append(movement)

    return movements


@transaction.atomic
def mark_movement_as_paid(movement, payment_comment=""):
    """
    Mark a financial movement as paid.
    """
    movement.status = FinancialMovement.MovementStatus.PAID
    movement.paid_at = timezone.localdate()
    movement.payment_comment = payment_comment or ""
    movement.save()

    return movement
