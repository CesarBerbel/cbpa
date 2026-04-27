from decimal import Decimal

from django.db import transaction

from finances.credit_card_services.date_service import get_invoice_reference_month
from finances.credit_card_services.invoice_service import (
    get_or_create_invoice,
    sync_invoice_payment_movement,
)
from finances.models import (
    CreditCardExpense,
    CreditCardInstallment,
    CreditCardInvoice,
    FinancialMovement,
)


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
    Create a credit card expense and its monthly installments.
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
