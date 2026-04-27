from datetime import date

from django.db.models import Sum

from finances.models import CreditCardInstallment


def get_credit_card_category_summary(card, year, month):
    """
    Return credit card spending grouped by category and subcategory.
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