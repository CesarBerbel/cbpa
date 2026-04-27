from django.db import transaction

from finances.models import FinancialMovement, FinancialTransfer
from finances.services.movement_service import get_manual_movement_initial_status


@transaction.atomic
def create_transfer(
    company,
    origin_account,
    destination_account,
    amount,
    due_date,
    description="",
):
    """
    Create a transfer between two financial accounts.
    """
    status = get_manual_movement_initial_status(due_date)

    origin_movement = FinancialMovement.objects.create(
        company=company,
        account=origin_account,
        movement_type=FinancialMovement.MovementType.EXPENSE,
        recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
        description=description or "Transferência enviada",
        amount=amount,
        due_date=due_date,
        status=status,
    )

    destination_movement = FinancialMovement.objects.create(
        company=company,
        account=destination_account,
        movement_type=FinancialMovement.MovementType.INCOME,
        recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
        description=description or "Transferência recebida",
        amount=amount,
        due_date=due_date,
        status=status,
    )

    return FinancialTransfer.objects.create(
        company=company,
        origin_account=origin_account,
        destination_account=destination_account,
        amount=amount,
        due_date=due_date,
        description=description,
        origin_movement=origin_movement,
        destination_movement=destination_movement,
    )