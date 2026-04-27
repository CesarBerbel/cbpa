import uuid
from calendar import monthrange
from datetime import date

from django.db import transaction

from finances.models import FinancialMovement
from finances.services.date_service import get_month_start_and_end
from finances.services.movement_service import get_manual_movement_initial_status


def get_fixed_occurrence_due_date(template, year, month):
    """
    Return a valid due date for a fixed movement occurrence.
    """
    last_day = monthrange(year, month)[1]
    day = min(template.due_date.day, last_day)

    return date(year, month, day)


@transaction.atomic
def create_fixed_movement_template(
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
    Create a fixed movement template.
    """
    return FinancialMovement.objects.create(
        company=company,
        account=account,
        movement_type=movement_type,
        category=category,
        subcategory=subcategory,
        recurrence_type=FinancialMovement.RecurrenceType.FIXED,
        description=description,
        amount=amount,
        due_date=due_date,
        status=FinancialMovement.MovementStatus.PENDING,
        fixed_group=str(uuid.uuid4()),
        is_fixed_template=True,
    )


@transaction.atomic
def ensure_fixed_movements_for_month(company, year, month):
    """
    Ensure fixed movement occurrences exist for the selected month.
    """
    month_start, month_end = get_month_start_and_end(
        year=year,
        month=month,
    )

    templates = FinancialMovement.objects.filter(
        company=company,
        recurrence_type=FinancialMovement.RecurrenceType.FIXED,
        is_fixed_template=True,
        due_date__lte=month_end,
    )

    created_movements = []

    for template in templates:
        occurrence_month = date(year, month, 1)

        exists = FinancialMovement.objects.filter(
            parent_fixed_movement=template,
            fixed_occurrence_month=occurrence_month,
        ).exists()

        if exists:
            continue

        occurrence_due_date = get_fixed_occurrence_due_date(
            template=template,
            year=year,
            month=month,
        )

        movement = FinancialMovement.objects.create(
            company=company,
            account=template.account,
            movement_type=template.movement_type,
            category=template.category,
            subcategory=template.subcategory,
            recurrence_type=FinancialMovement.RecurrenceType.FIXED,
            description=template.description,
            amount=template.amount,
            due_date=occurrence_due_date,
            status=get_manual_movement_initial_status(occurrence_due_date),
            fixed_group=template.fixed_group,
            is_fixed_template=False,
            parent_fixed_movement=template,
            fixed_occurrence_month=occurrence_month,
        )

        created_movements.append(movement)

    return created_movements
