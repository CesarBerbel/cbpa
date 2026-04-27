from datetime import date

from dateutil.relativedelta import relativedelta

from finances.services.date_service import get_safe_month_date


def get_invoice_reference_month(card, purchase_date, installment_index=0):
    """
    Calculate the invoice reference month for a credit card purchase.
    """
    reference = date(purchase_date.year, purchase_date.month, 1)

    if purchase_date.day > card.closing_day:
        reference = reference + relativedelta(months=1)

    return reference + relativedelta(months=installment_index)


def get_invoice_dates(card, reference_month):
    """
    Return closing date and due date for an invoice.
    """
    closing_date = get_safe_month_date(
        year=reference_month.year,
        month=reference_month.month,
        day=card.closing_day,
    )

    due_date = get_safe_month_date(
        year=reference_month.year,
        month=reference_month.month,
        day=card.due_day,
    )

    if due_date <= closing_date:
        due_date = due_date + relativedelta(months=1)

    return closing_date, due_date
