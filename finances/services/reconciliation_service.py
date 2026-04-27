import hashlib

from finances.models import FinancialMovement


def build_statement_reference(account, movement_date, description, amount, line_number):
    """
    Build a stable external reference for imported bank statement rows.
    """
    raw = f"{account.id}|{movement_date}|{description}|{amount}|{line_number}"

    return hashlib.sha256(raw.encode()).hexdigest()


def find_matching_manual_movement(
    company,
    account,
    movement_type,
    amount,
    movement_date,
):
    """
    Find a compatible pending or overdue manual movement for reconciliation.
    """
    return (
        FinancialMovement.objects.filter(
            company=company,
            account=account,
            movement_type=movement_type,
            amount=amount,
            status__in=[
                FinancialMovement.MovementStatus.PENDING,
                FinancialMovement.MovementStatus.OVERDUE,
            ],
            is_imported=False,
            paid_at__isnull=True,
            due_date__lte=movement_date,
        )
        .order_by(
            "-due_date",
            "-id",
        )
        .first()
    )