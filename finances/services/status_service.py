from django.db import transaction
from django.utils import timezone

from finances.models import FinancialMovement


@transaction.atomic
def update_overdue_financial_movements():
    """
    Update pending movements to overdue.
    """
    today = timezone.localdate()

    return FinancialMovement.objects.filter(
        status=FinancialMovement.MovementStatus.PENDING,
        due_date__lt=today,
    ).update(
        status=FinancialMovement.MovementStatus.OVERDUE,
    )