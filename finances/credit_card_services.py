from calendar import monthrange
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import Sum

from finances.models import (
    CreditCard,
    CreditCardExpense,
    CreditCardInstallment,
    CreditCardInvoice,
    FinancialMovement,
)


def get_safe_month_date(year, month, day):
    """
    Return a valid date using the last day of month when needed.
    """
    last_day = monthrange(year, month)[1]
    safe_day = min(day, last_day)

    return date(year, month, safe_day)


def get_invoice_reference_month(card, purchase_date, installment_index=0):
    """
    Calculate invoice reference month.

    If the purchase is after closing day, it goes to next invoice.
    Then installment_index advances month by month.
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


@transaction.atomic
def get_or_create_invoice(card, reference_month):
    """
    Get or create a credit card invoice for the reference month.
    """
    closing_date, due_date = get_invoice_dates(
        card=card,
        reference_month=reference_month,
    )

    invoice, _ = CreditCardInvoice.objects.get_or_create(
        card=card,
        reference_month=reference_month,
        defaults={
            "closing_date": closing_date,
            "due_date": due_date,
        },
    )

    return invoice


@transaction.atomic
def sync_invoice_payment_movement(invoice):
    """
    Create or update the financial movement linked to the invoice.

    This movement is pending in the payment account and enters expected balance.
    """
    total = (
        invoice.installments.aggregate(
            total=Sum("amount"),
        )["total"]
        or Decimal("0.00")
    )

    invoice.total_amount = total

    if total <= 0:
        if invoice.payment_movement and invoice.payment_movement.status != FinancialMovement.MovementStatus.PAID:
            invoice.payment_movement.delete()
            invoice.payment_movement = None

        invoice.save(
            update_fields=[
                "total_amount",
                "payment_movement",
                "updated_at",
            ]
        )
        return invoice

    if invoice.payment_movement:
        movement = invoice.payment_movement

        if movement.status != FinancialMovement.MovementStatus.PAID:
            movement.amount = total
            movement.due_date = invoice.due_date
            movement.description = f"Fatura {invoice.card} {invoice.reference_month:%m/%Y}"
            movement.save(
                update_fields=[
                    "amount",
                    "due_date",
                    "description",
                    "updated_at",
                ]
            )
    else:
        movement = FinancialMovement.objects.create(
            company=invoice.card.company,
            account=invoice.card.payment_account,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
            description=f"Fatura {invoice.card} {invoice.reference_month:%m/%Y}",
            amount=total,
            due_date=invoice.due_date,
            status=FinancialMovement.MovementStatus.PENDING,
        )

        invoice.payment_movement = movement

    invoice.save(
        update_fields=[
            "total_amount",
            "payment_movement",
            "updated_at",
        ]
    )

    return invoice


@transaction.atomic
def create_credit_card_expense(
    card,
    description,
    purchase_date,
    total_amount,
    installments,
    category=None,
    subcategory=None,
):
    """
    Create credit card expense and all monthly installments.
    """
    expense = CreditCardExpense.objects.create(
        card=card,
        description=description,
        purchase_date=purchase_date,
        total_amount=total_amount,
        installments=installments,
        category=category,
        subcategory=subcategory,
    )

    installment_amount = total_amount / Decimal(installments)

    invoices_to_sync = set()

    for index in range(installments):
        reference_month = get_invoice_reference_month(
            card=card,
            purchase_date=purchase_date,
            installment_index=index,
        )

        invoice = get_or_create_invoice(
            card=card,
            reference_month=reference_month,
        )

        CreditCardInstallment.objects.create(
            expense=expense,
            invoice=invoice,
            installment_number=index + 1,
            installment_total=installments,
            amount=installment_amount,
            category=category,
            subcategory=subcategory,
        )

        invoices_to_sync.add(invoice.id)

    for invoice in CreditCardInvoice.objects.filter(id__in=invoices_to_sync):
        sync_invoice_payment_movement(invoice)

    return expense


@transaction.atomic
def delete_credit_card_expense(expense):
    """
    Delete a credit card expense only if none of its invoices are paid.
    """
    paid_invoice_exists = CreditCardInvoice.objects.filter(
        installments__expense=expense,
        status=CreditCardInvoice.InvoiceStatus.PAID,
    ).exists()

    paid_movement_exists = FinancialMovement.objects.filter(
        credit_card_invoice__installments__expense=expense,
        status=FinancialMovement.MovementStatus.PAID,
    ).exists()

    if paid_invoice_exists or paid_movement_exists:
        raise ValueError("Não é possível excluir gasto com fatura já efetivada.")

    invoice_ids = list(
        CreditCardInvoice.objects.filter(
            installments__expense=expense,
        ).values_list(
            "id",
            flat=True,
        )
    )

    expense.delete()

    for invoice in CreditCardInvoice.objects.filter(id__in=invoice_ids):
        sync_invoice_payment_movement(invoice)


@transaction.atomic
def sync_paid_invoice_from_movement(movement):
    """
    Mark invoice as paid when its financial movement is paid.
    """
    invoice = getattr(
        movement,
        "credit_card_invoice",
        None,
    )

    if not invoice:
        return None

    invoice.status = CreditCardInvoice.InvoiceStatus.PAID
    invoice.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    return invoice


def get_credit_card_category_summary(card, year, month):
    """
    Return card spending grouped by category/subcategory in a month.
    """
    reference_month = date(year, month, 1)

    return (
        CreditCardInstallment.objects.filter(
            invoice__card=card,
            invoice__reference_month=reference_month,
        )
        .values(
            "category__name",
            "subcategory__name",
        )
        .annotate(
            total=Sum("amount"),
        )
        .order_by(
            "category__name",
            "subcategory__name",
        )
    )

def ensure_credit_card_invoices_for_month(company, year, month):
    """
    Ensure invoices and payment movements are synchronized for all company cards.
    """
    reference_month = date(year, month, 1)

    cards = CreditCard.objects.filter(
        company=company,
        is_active=True,
    )

    invoices = []

    for card in cards:
        invoice = get_or_create_invoice(
            card=card,
            reference_month=reference_month,
        )

        sync_invoice_payment_movement(invoice)

        invoices.append(invoice)

    return invoices