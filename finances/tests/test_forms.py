from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from companies.models import Company
from finances.forms import (
    FinancialAccountForm,
    FinancialMovementForm,
    FinancialSubcategoryForm,
)
from finances.models import (
    Bank,
    FinancialAccount,
    FinancialCategory,
    FinancialSubcategory,
    FinancialMovement,
)

User = get_user_model()


class FinanceFormsTestCase(TestCase):
    """
    Tests for finance forms.
    """

    def setUp(self):
        """
        Create base company, users, bank, account and categories.
        """
        self.company_user = User.objects.create_user(
            nif="500000001",
            email="empresa@example.com",
            password="Testpass123",
            full_name="Empresa Teste",
            user_type=User.UserType.COMPANY,
        )

        self.person_user = User.objects.create_user(
            nif="123456789",
            email="pessoa@example.com",
            password="Testpass123",
            full_name="Pessoa Teste",
            user_type=User.UserType.PERSON,
        )

        self.company = Company.objects.create(
            user=self.company_user,
            name="Empresa Teste",
            nif="500000001",
            email="empresa@example.com",
        )

        self.bank = Bank.objects.create(
            company=self.company,
            name="Santander",
        )

        self.account = FinancialAccount.objects.create(
            company=self.company,
            bank=self.bank,
            holder=self.company_user,
            initial_balance=Decimal("1000.00"),
        )

        self.income_category = FinancialCategory.objects.create(
            company=self.company,
            movement_type=FinancialMovement.MovementType.INCOME,
            name="Receitas operacionais",
        )

        self.expense_category = FinancialCategory.objects.create(
            company=self.company,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            name="Despesas operacionais",
        )

        self.expense_subcategory = FinancialSubcategory.objects.create(
            company=self.company,
            category=self.expense_category,
            name="Fornecedores",
        )

    def test_financial_account_form_rejects_duplicate_holder_bank(self):
        """
        The same holder cannot have two accounts for the same bank in the same company.
        """
        form = FinancialAccountForm(
            data={
                "bank": self.bank.id,
                "holder": self.company_user.id,
                "initial_balance": "500.00",
            },
            company=self.company,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Este titular já possui uma conta financeira para este banco nesta empresa.",
            str(form.errors),
        )

    def test_movement_form_rejects_category_from_wrong_type(self):
        """
        Expense movement cannot use income category.
        """
        form = FinancialMovementForm(
            data={
                "account": self.account.id,
                "movement_type": FinancialMovement.MovementType.EXPENSE,
                "recurrence_type": FinancialMovement.RecurrenceType.SINGLE,
                "category": self.income_category.id,
                "amount": "100.00",
                "due_date": "2026-01-10",
                "description": "Despesa com categoria errada",
            },
            company=self.company,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "A categoria selecionada não pertence ao tipo de movimentação escolhido.",
            str(form.errors),
        )

    def test_movement_form_rejects_subcategory_from_wrong_category(self):
        """
        Subcategory must belong to the selected category.
        """
        form = FinancialMovementForm(
            data={
                "account": self.account.id,
                "movement_type": FinancialMovement.MovementType.INCOME,
                "recurrence_type": FinancialMovement.RecurrenceType.SINGLE,
                "category": self.income_category.id,
                "subcategory": self.expense_subcategory.id,
                "amount": "100.00",
                "due_date": "2026-01-10",
                "description": "Receita com subcategoria errada",
            },
            company=self.company,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "A subcategoria selecionada não pertence à categoria escolhida.",
            str(form.errors),
        )

    def test_movement_form_accepts_valid_expense_category_and_subcategory(self):
        """
        Valid expense category and subcategory should be accepted.
        """
        form = FinancialMovementForm(
            data={
                "account": self.account.id,
                "movement_type": FinancialMovement.MovementType.EXPENSE,
                "recurrence_type": FinancialMovement.RecurrenceType.SINGLE,
                "category": self.expense_category.id,
                "subcategory": self.expense_subcategory.id,
                "amount": "100.00",
                "due_date": "2026-01-10",
                "description": "Despesa válida",
            },
            company=self.company,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_installment_movement_requires_installments(self):
        """
        Installment movement must include number of installments and amount mode.
        """
        form = FinancialMovementForm(
            data={
                "account": self.account.id,
                "movement_type": FinancialMovement.MovementType.EXPENSE,
                "recurrence_type": FinancialMovement.RecurrenceType.INSTALLMENT,
                "amount": "300.00",
                "due_date": "2026-01-10",
                "description": "Parcelado inválido",
            },
            company=self.company,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Informe o número de parcelas.",
            str(form.errors),
        )

    def test_subcategory_form_filters_categories_by_company(self):
        """
        Subcategory form should only show categories from current company.
        """
        other_user = User.objects.create_user(
            nif="500000002",
            email="outra@example.com",
            password="Testpass123",
            full_name="Outra Empresa",
            user_type=User.UserType.COMPANY,
        )

        other_company = Company.objects.create(
            user=other_user,
            name="Outra Empresa",
            nif="500000002",
        )

        other_category = FinancialCategory.objects.create(
            company=other_company,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            name="Categoria externa",
        )

        form = FinancialSubcategoryForm(
            company=self.company,
        )

        self.assertIn(
            self.expense_category,
            form.fields["category"].queryset,
        )

        self.assertNotIn(
            other_category,
            form.fields["category"].queryset,
        )