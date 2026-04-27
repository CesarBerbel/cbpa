from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from finances.credit_card_services.date_service import get_invoice_dates
from finances.models import CreditCard, CreditCardInvoice, FinancialMovement


@transaction.atomic
def get_or_create_invoice(card, reference_month):
    """
    Get or create a credit card invoice for a reference month.
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
    """
    total = (
        invoice.installments.aggregate(
            total=Sum("amount"),
        )["total"]
        or Decimal("0.00")
    )

    invoice.total_amount = total

    if total <= 0:
        if (
            invoice.payment_movement
            and invoice.payment_movement.status != FinancialMovement.MovementStatus.PAID
        ):
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
def sync_paid_invoice_from_movement(movement):
    """
    Mark invoice as paid when its linked financial movement is paid.
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


def ensure_credit_card_invoices_for_month(company, year, month):
    """
    Ensure invoices and payment movements exist for all active company cards.
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