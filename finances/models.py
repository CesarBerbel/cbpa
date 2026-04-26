from decimal import Decimal

from django.conf import settings
from django.db import models

from companies.models import Company


class Bank(models.Model):
    """
    Bank registered for a company.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="banks",
        verbose_name="Empresa",
    )

    name = models.CharField(
        max_length=120,
        verbose_name="Nome do banco",
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
        verbose_name = "Banco"
        verbose_name_plural = "Bancos"
        ordering = ["name"]

    def __str__(self):
        return self.name


class FinancialAccount(models.Model):
    """
    Financial account owned by a company or linked person.

    A holder cannot have two accounts for the same bank inside the same company.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="financial_accounts",
        verbose_name="Empresa",
    )

    bank = models.ForeignKey(
        Bank,
        on_delete=models.PROTECT,
        related_name="financial_accounts",
        verbose_name="Banco",
    )

    holder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="financial_accounts",
        verbose_name="Titular",
    )

    initial_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Saldo inicial",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativa",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criada em",
    )

    class Meta:
        verbose_name = "Conta financeira"
        verbose_name_plural = "Contas financeiras"
        ordering = [
            "bank__name",
            "holder__full_name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "bank",
                    "holder",
                ],
                name="unique_financial_account_per_company_bank_holder",
            ),
        ]

    def __str__(self):
        return f"{self.bank.name} - {self.holder.full_name}"

    @property
    def name(self):
        """Return account name from bank."""
        return self.bank.name


class FinancialMovement(models.Model):
    """
    Financial movement for income, expense or transfer.
    """

    class MovementType(models.TextChoices):
        INCOME = "INCOME", "Entrada"
        EXPENSE = "EXPENSE", "Saída"

    class MovementStatus(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        PAID = "PAID", "Efetuada"
        OVERDUE = "OVERDUE", "Atrasada"

    class RecurrenceType(models.TextChoices):
        SINGLE = "SINGLE", "Único"
        INSTALLMENT = "INSTALLMENT", "Parcelado"
        FIXED = "FIXED", "Fixo"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="financial_movements",
        verbose_name="Empresa",
    )

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.CASCADE,
        related_name="movements",
        verbose_name="Conta",
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
        verbose_name="Tipo",
    )

    category = models.ForeignKey(
        "FinancialCategory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
        verbose_name="Categoria",
    )

    subcategory = models.ForeignKey(
        "FinancialSubcategory",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
        verbose_name="Subcategoria",
    )

    recurrence_type = models.CharField(
        max_length=20,
        choices=RecurrenceType.choices,
        default=RecurrenceType.SINGLE,
        verbose_name="Recorrência",
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Descrição",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Valor",
    )

    due_date = models.DateField(
        verbose_name="Data de vencimento",
    )

    status = models.CharField(
        max_length=20,
        choices=MovementStatus.choices,
        default=MovementStatus.PENDING,
        verbose_name="Status",
    )

    installment_group = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="Grupo de parcelamento",
    )

    installment_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Número da parcela",
    )

    installment_total = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Total de parcelas",
    )

    fixed_group = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="Grupo fixo",
    )

    is_imported = models.BooleanField(
        default=False,
        verbose_name="Importado",
    )

    is_fixed_template = models.BooleanField(
        default=False,
        verbose_name="É modelo fixo",
    )

    parent_fixed_movement = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="fixed_occurrences",
        verbose_name="Movimento fixo de origem",
    )

    fixed_occurrence_month = models.DateField(
        null=True,
        blank=True,
        verbose_name="Mês da ocorrência fixa",
    )

    paid_at = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de efetivação",
    )

    payment_comment = models.TextField(
        blank=True,
        verbose_name="Comentário da efetivação",
    )

    external_reference = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Referência externa",
    )

    is_reconciled = models.BooleanField(
        default=False,
        verbose_name="Conciliado",
    )

    reconciled_with = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matched_movements",
        verbose_name="Conciliado com",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em",
    )

    class Meta:
        verbose_name = "Movimento financeiro"
        verbose_name_plural = "Movimentos financeiros"
        ordering = ["-due_date", "-created_at"]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.amount} EUR"

    @property
    def signed_amount(self):
        """Return positive amount for income and negative amount for expense."""
        if self.movement_type == self.MovementType.INCOME:
            return self.amount

        return self.amount * Decimal("-1")


class FinancialTransfer(models.Model):
    """
    Transfer between two financial accounts.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="financial_transfers",
        verbose_name="Empresa",
    )

    origin_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="outgoing_transfers",
        verbose_name="Conta de origem",
    )

    destination_account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="incoming_transfers",
        verbose_name="Conta de destino",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Valor",
    )

    due_date = models.DateField(
        verbose_name="Data",
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Descrição",
    )

    origin_movement = models.OneToOneField(
        FinancialMovement,
        on_delete=models.PROTECT,
        related_name="origin_transfer",
        verbose_name="Movimento de saída",
    )

    destination_movement = models.OneToOneField(
        FinancialMovement,
        on_delete=models.PROTECT,
        related_name="destination_transfer",
        verbose_name="Movimento de entrada",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criada em",
    )

    class Meta:
        verbose_name = "Transferência financeira"
        verbose_name_plural = "Transferências financeiras"
        ordering = ["-due_date"]

    def __str__(self):
        return (
            f"{self.origin_account} -> {self.destination_account} - {self.amount} EUR"
        )


class BankStatementImport(models.Model):
    """
    Stores each imported bank statement transaction for audit purposes.
    """

    class ImportStatus(models.TextChoices):
        IMPORTED = "IMPORTED", "Importado"
        MATCHED = "MATCHED", "Conciliado"
        DUPLICATED = "DUPLICATED", "Duplicado"
        INVALID = "INVALID", "Inválido"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="statement_imports",
    )

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.CASCADE,
        related_name="statement_imports",
    )

    movement = models.ForeignKey(
        FinancialMovement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="statement_entries",
    )

    date = models.DateField()

    description = models.CharField(
        max_length=255,
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    external_reference = models.CharField(
        max_length=255,
    )

    status = models.CharField(
        max_length=20,
        choices=ImportStatus.choices,
    )

    raw_line = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.date} - {self.amount} - {self.get_status_display()}"


class FinancialCategory(models.Model):
    """
    Financial category by movement type.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="financial_categories",
        verbose_name="Empresa",
    )

    movement_type = models.CharField(
        max_length=20,
        choices=(
            FinancialMovement.MovementType.choices
            if "FinancialMovement" in globals()
            else [
                ("INCOME", "Entrada"),
                ("EXPENSE", "Saída"),
            ]
        ),
        verbose_name="Tipo de movimentação",
    )

    name = models.CharField(
        max_length=120,
        verbose_name="Categoria",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativa",
    )

    class Meta:
        verbose_name = "Categoria financeira"
        verbose_name_plural = "Categorias financeiras"
        ordering = ["movement_type", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "movement_type", "name"],
                name="unique_financial_category_per_company_type",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_movement_type_display()}"


class FinancialSubcategory(models.Model):
    """
    Financial subcategory linked to a financial category.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="financial_subcategories",
        verbose_name="Empresa",
    )

    category = models.ForeignKey(
        FinancialCategory,
        on_delete=models.CASCADE,
        related_name="subcategories",
        verbose_name="Categoria",
    )

    name = models.CharField(
        max_length=120,
        verbose_name="Subcategoria",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativa",
    )

    class Meta:
        verbose_name = "Subcategoria financeira"
        verbose_name_plural = "Subcategorias financeiras"
        ordering = ["category__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "category", "name"],
                name="unique_financial_subcategory_per_category",
            ),
        ]

    def __str__(self):
        return f"{self.category.name} > {self.name}"
