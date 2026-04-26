from django.contrib import admin

from finances.models import Bank, FinancialAccount, FinancialMovement, FinancialTransfer,FinancialCategory,FinancialSubcategory


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