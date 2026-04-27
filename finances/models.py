from decimal import Decimal

from django.db import models
from django.utils import timezone

from companies.models import Company
from accounts.models import User


# =========================================
# BANK
# =========================================

class Bank(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="banks",
    )

    name = models.CharField(
        max_length=120,
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name"],
                name="unique_bank_per_company",
            )
        ]

    def __str__(self):
        return self.name


# =========================================
# ACCOUNT
# =========================================

class FinancialAccount(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="accounts",
    )

    bank = models.ForeignKey(
        'Bank',
        on_delete=models.CASCADE,
        related_name="accounts",
    )

    holder = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="accounts",
    )

    initial_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativa",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "bank", "holder"],
                name="unique_account_per_holder_bank_company",
            )
        ]

    def __str__(self):
        return f"{self.bank.name} - {self.holder.full_name}"


# =========================================
# CATEGORY (ANTES DE MOVEMENT)
# =========================================

class FinancialCategory(models.Model):
    class MovementType(models.TextChoices):
        INCOME = "INCOME", "Entrada"
        EXPENSE = "EXPENSE", "Saída"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="categories",
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )

    name = models.CharField(max_length=120)

    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "movement_type", "name"],
                name="unique_category_per_company_type",
            )
        ]

    def __str__(self):
        return f"{self.name}"


class FinancialSubcategory(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="subcategories",
    )

    category = models.ForeignKey(
        FinancialCategory,
        on_delete=models.CASCADE,
        related_name="subcategories",
    )

    name = models.CharField(max_length=120)

    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "category", "name"],
                name="unique_subcategory_per_category",
            )
        ]

    def __str__(self):
        return f"{self.category.name} > {self.name}"


# =========================================
# MOVEMENT
# =========================================

class FinancialMovement(models.Model):
    class MovementType(models.TextChoices):
        INCOME = "INCOME", "Entrada"
        EXPENSE = "EXPENSE", "Saída"

    class RecurrenceType(models.TextChoices):
        SINGLE = "SINGLE", "Único"
        INSTALLMENT = "INSTALLMENT", "Parcelado"
        FIXED = "FIXED", "Fixo"

    class MovementStatus(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        OVERDUE = "OVERDUE", "Atrasado"
        PAID = "PAID", "Pago"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="movements",
    )

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.CASCADE,
        related_name="movements",
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )

    category = models.ForeignKey(
        FinancialCategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    subcategory = models.ForeignKey(
        FinancialSubcategory,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    recurrence_type = models.CharField(
        max_length=20,
        choices=RecurrenceType.choices,
    )

    description = models.TextField(blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    due_date = models.DateField()

    paid_at = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=MovementStatus.choices,
    )

    # IMPORT / MATCH
    is_imported = models.BooleanField(default=False)
    is_reconciled = models.BooleanField(default=False)
    external_reference = models.CharField(max_length=255, blank=True)

    # INSTALLMENTS
    installment_group = models.CharField(max_length=100, blank=True)
    installment_number = models.IntegerField(null=True, blank=True)
    installment_total = models.IntegerField(null=True, blank=True)

    # FIXED
    fixed_group = models.CharField(max_length=100, blank=True)
    is_fixed_template = models.BooleanField(default=False)
    parent_fixed_movement = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="fixed_children",
    )
    fixed_occurrence_month = models.DateField(null=True, blank=True)

    payment_comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def signed_amount(self):
        if self.movement_type == self.MovementType.EXPENSE:
            return -self.amount
        return self.amount

    def __str__(self):
        return f"{self.description} - {self.amount}"


# =========================================
# TRANSFER
# =========================================

class FinancialTransfer(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
    )

    origin_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.CASCADE,
        related_name="transfers_out",
    )

    destination_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.CASCADE,
        related_name="transfers_in",
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    due_date = models.DateField()

    description = models.TextField(blank=True)

    origin_movement = models.ForeignKey(
        FinancialMovement,
        on_delete=models.CASCADE,
        related_name="transfer_origin",
    )

    destination_movement = models.ForeignKey(
        FinancialMovement,
        on_delete=models.CASCADE,
        related_name="transfer_destination",
    )


# =========================================
# IMPORT AUDIT (COM IA)
# =========================================

class BankStatementImport(models.Model):
    class ImportStatus(models.TextChoices):
        IMPORTED = "IMPORTED", "Importado"
        MATCHED = "MATCHED", "Conciliado"
        DUPLICATED = "DUPLICATED", "Duplicado"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
    )

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.CASCADE,
    )

    movement = models.ForeignKey(
        FinancialMovement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    date = models.DateField()

    description = models.TextField()

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    external_reference = models.CharField(max_length=255)

    status = models.CharField(
        max_length=20,
        choices=ImportStatus.choices,
    )

    raw_line = models.TextField(blank=True)

    # IA
    suggested_category = models.ForeignKey(
        FinancialCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    suggested_subcategory = models.ForeignKey(
        FinancialSubcategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    categorization_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    categorization_source = models.CharField(max_length=20, blank=True)

    categorization_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)


class CreditCard(models.Model):
    """
    Credit card linked to a financial payment account.
    """

    class CardBrand(models.TextChoices):
        VISA = "VISA", "Visa"
        MASTERCARD = "MASTERCARD", "Mastercard"
        AMEX = "AMEX", "American Express"
        OTHER = "OTHER", "Outro"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="credit_cards",
        verbose_name="Empresa",
    )

    payment_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="credit_cards",
        verbose_name="Conta de pagamento",
    )

    brand = models.CharField(
        max_length=30,
        choices=CardBrand.choices,
        verbose_name="Bandeira",
    )

    last_digits = models.CharField(
        max_length=4,
        verbose_name="Final do cartão",
    )

    limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Limite",
    )

    closing_day = models.PositiveSmallIntegerField(
        verbose_name="Dia de fecho",
    )

    due_day = models.PositiveSmallIntegerField(
        verbose_name="Dia de vencimento",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em",
    )

    class Meta:
        verbose_name = "Cartão de crédito"
        verbose_name_plural = "Cartões de crédito"
        ordering = ["brand", "last_digits"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "payment_account", "last_digits"],
                name="unique_credit_card_per_account_last_digits",
            ),
        ]

    def __str__(self):
        return f"{self.get_brand_display()} final {self.last_digits}"


class CreditCardExpense(models.Model):
    """
    Purchase made with a credit card.
    """

    card = models.ForeignKey(
        CreditCard,
        on_delete=models.CASCADE,
        related_name="expenses",
        verbose_name="Cartão",
    )

    category = models.ForeignKey(
        "FinancialCategory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_card_expenses",
        verbose_name="Categoria",
    )

    subcategory = models.ForeignKey(
        "FinancialSubcategory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_card_expenses",
        verbose_name="Subcategoria",
    )

    description = models.CharField(
        max_length=255,
        verbose_name="Descrição",
    )

    purchase_date = models.DateField(
        verbose_name="Data da compra",
    )

    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Valor total",
    )

    installments = models.PositiveIntegerField(
        default=1,
        verbose_name="Parcelas",
    )

    is_deleted = models.BooleanField(
        default=False,
        verbose_name="Excluído",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em",
    )

    class Meta:
        verbose_name = "Gasto de cartão"
        verbose_name_plural = "Gastos de cartão"
        ordering = ["-purchase_date", "-created_at"]

    def __str__(self):
        return f"{self.description} - {self.total_amount} EUR"


class CreditCardInvoice(models.Model):
    """
    Monthly credit card invoice.

    Each invoice creates one pending financial movement in the payment account.
    """

    class InvoiceStatus(models.TextChoices):
        OPEN = "OPEN", "Aberta"
        PAID = "PAID", "Efetuada"
        CANCELED = "CANCELED", "Cancelada"

    card = models.ForeignKey(
        CreditCard,
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name="Cartão",
    )

    reference_month = models.DateField(
        verbose_name="Mês de referência",
    )

    closing_date = models.DateField(
        verbose_name="Data de fecho",
    )

    due_date = models.DateField(
        verbose_name="Data de vencimento",
    )

    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Valor total",
    )

    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.OPEN,
        verbose_name="Status",
    )

    payment_movement = models.OneToOneField(
        FinancialMovement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_card_invoice",
        verbose_name="Movimento financeiro da fatura",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criada em",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizada em",
    )

    class Meta:
        verbose_name = "Fatura de cartão"
        verbose_name_plural = "Faturas de cartão"
        ordering = ["-reference_month"]
        constraints = [
            models.UniqueConstraint(
                fields=["card", "reference_month"],
                name="unique_credit_card_invoice_per_month",
            ),
        ]

    def __str__(self):
        return f"{self.card} - {self.reference_month:%m/%Y}"


class CreditCardInstallment(models.Model):
    """
    One installment of a credit card expense.
    """

    expense = models.ForeignKey(
        CreditCardExpense,
        on_delete=models.CASCADE,
        related_name="expense_installments",
        verbose_name="Gasto",
    )

    invoice = models.ForeignKey(
        CreditCardInvoice,
        on_delete=models.CASCADE,
        related_name="installments",
        verbose_name="Fatura",
    )

    installment_number = models.PositiveIntegerField(
        verbose_name="Número da parcela",
    )

    installment_total = models.PositiveIntegerField(
        verbose_name="Total de parcelas",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Valor",
    )

    category = models.ForeignKey(
        "FinancialCategory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_card_installments",
        verbose_name="Categoria",
    )

    subcategory = models.ForeignKey(
        "FinancialSubcategory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_card_installments",
        verbose_name="Subcategoria",
    )

    class Meta:
        verbose_name = "Parcela de cartão"
        verbose_name_plural = "Parcelas de cartão"
        ordering = ["invoice__reference_month", "installment_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["expense", "installment_number"],
                name="unique_credit_card_expense_installment",
            ),
        ]

    def __str__(self):
        return f"{self.expense.description} {self.installment_number}/{self.installment_total}"    