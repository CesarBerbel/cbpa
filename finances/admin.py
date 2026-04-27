from django.contrib import admin

from finances.models import (
    Bank,
    BankStatementImport,
    FinancialAccount,
    FinancialMovement,
    FinancialTransfer,
    FinancialCategory,
    FinancialSubcategory,
    CreditCard,
    CreditCardExpense,
    CreditCardInvoice,
    CreditCardInstallment,
)


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    """
    Admin for banks.
    """

    list_display = [
        "name",
        "company",
        "is_active",
    ]

    list_filter = [
        "company",
        "is_active",
    ]

    search_fields = [
        "name",
        "company__name",
    ]


@admin.register(FinancialAccount)
class FinancialAccountAdmin(admin.ModelAdmin):
    """
    Admin for financial accounts.
    """

    list_display = [
        "bank",
        "company",
        "holder",
        "initial_balance",
        "is_active",
    ]

    list_filter = [
        "company",
        "bank",
        "is_active",
    ]

    search_fields = [
        "bank__name",
        "holder__full_name",
        "holder__nif",
    ]


@admin.register(FinancialMovement)
class FinancialMovementAdmin(admin.ModelAdmin):
    """
    Admin for financial movements.
    """

    list_display = [
        "company",
        "account",
        "movement_type",
        "recurrence_type",
        "amount",
        "due_date",
        "status",
        "is_imported",
    ]

    list_filter = [
        "company",
        "movement_type",
        "recurrence_type",
        "status",
        "is_imported",
    ]

    search_fields = [
        "description",
        "account__bank__name",
    ]


@admin.register(FinancialTransfer)
class FinancialTransferAdmin(admin.ModelAdmin):
    """
    Admin for financial transfers.
    """

    list_display = [
        "company",
        "origin_account",
        "destination_account",
        "amount",
        "due_date",
    ]

    list_filter = [
        "company",
        "due_date",
    ]


@admin.register(FinancialCategory)
class FinancialCategoryAdmin(admin.ModelAdmin):
    """
    Admin for financial categories.
    """

    list_display = [
        "company",
        "movement_type",
        "name",
        "is_active",
    ]

    list_filter = [
        "company",
        "movement_type",
        "is_active",
    ]

    search_fields = [
        "name",
        "company__name",
    ]


@admin.register(FinancialSubcategory)
class FinancialSubcategoryAdmin(admin.ModelAdmin):
    """
    Admin for financial subcategories.
    """

    list_display = [
        "company",
        "category",
        "name",
        "is_active",
    ]

    list_filter = [
        "company",
        "category",
        "is_active",
    ]

    search_fields = [
        "name",
        "category__name",
        "company__name",
    ]

# =========================================
# CREDIT CARD
# =========================================

@admin.register(CreditCard)
class CreditCardAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "company",
        "payment_account",
        "brand",
        "last_digits",
        "limit",
        "closing_day",
        "due_day",
        "is_active",
    )
    list_filter = ("company", "brand", "is_active")
    search_fields = ("last_digits", "payment_account__bank__name")


# =========================================
# CREDIT CARD EXPENSE
# =========================================

@admin.register(CreditCardExpense)
class CreditCardExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "card",
        "description",
        "purchase_date",
        "total_amount",
        "installments",
        "category",
        "subcategory",
        "is_deleted",
    )
    list_filter = ("card", "category", "subcategory", "is_deleted")
    search_fields = ("description",)
    date_hierarchy = "purchase_date"


# =========================================
# INSTALLMENT INLINE
# =========================================

class CreditCardInstallmentInline(admin.TabularInline):
    model = CreditCardInstallment
    extra = 0
    readonly_fields = (
        "expense",
        "installment_number",
        "installment_total",
        "amount",
        "category",
        "subcategory",
    )


# =========================================
# CREDIT CARD INVOICE
# =========================================

@admin.register(CreditCardInvoice)
class CreditCardInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "card",
        "reference_month",
        "closing_date",
        "due_date",
        "total_amount",
        "status",
    )
    list_filter = ("card", "status")
    date_hierarchy = "reference_month" 
    inlines = [CreditCardInstallmentInline]

# =========================================
# IMPORT AUDIT
# =========================================

@admin.register(BankStatementImport)
class BankStatementImportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "company",
        "account",
        "date",
        "amount",
        "status",
        "suggested_category",
        "categorization_source",
    )
    list_filter = ("status", "company")
    search_fields = ("description",)