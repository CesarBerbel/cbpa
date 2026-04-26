from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from companies.models import Company
from finances.models import (
    Bank,
    FinancialAccount,
    FinancialCategory,
    FinancialMovement,
    FinancialSubcategory,
)

User = get_user_model()


class FinanceModelsTestCase(TestCase):
    """
    Tests for finance models.
    """

    def setUp(self):
        self.company_user = User.objects.create_user(
            nif="500000001",
            email="company@example.com",
            password="Testpass123",
            full_name="Company Test",
            user_type=User.UserType.COMPANY,
        )

        self.company = Company.objects.create(
            user=self.company_user,
            name="Company Test",
            nif="500000001",
            email="company@example.com",
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

    def test_bank_string(self):
        self.assertEqual(str(self.bank), "Santander")

    def test_account_name_comes_from_bank(self):
        self.assertEqual(self.account.name, "Santander")

    def test_account_string(self):
        self.assertIn("Santander", str(self.account))
        self.assertIn("Company Test", str(self.account))

    def test_income_signed_amount_is_positive(self):
        movement = FinancialMovement.objects.create(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.INCOME,
            recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
            amount=Decimal("100.00"),
            due_date="2026-01-10",
        )

        self.assertEqual(movement.signed_amount, Decimal("100.00"))

    def test_expense_signed_amount_is_negative(self):
        movement = FinancialMovement.objects.create(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
            amount=Decimal("100.00"),
            due_date="2026-01-10",
        )

        self.assertEqual(movement.signed_amount, Decimal("-100.00"))

    def test_category_string(self):
        category = FinancialCategory.objects.create(
            company=self.company,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            name="Suppliers",
        )

        self.assertIn("Suppliers", str(category))

    def test_subcategory_string(self):
        category = FinancialCategory.objects.create(
            company=self.company,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            name="Suppliers",
        )

        subcategory = FinancialSubcategory.objects.create(
            company=self.company,
            category=category,
            name="Food",
        )

        self.assertIn("Suppliers", str(subcategory))
        self.assertIn("Food", str(subcategory))

    def test_duplicate_bank_name_per_company_is_rejected(self):
        with self.assertRaises(IntegrityError):
            Bank.objects.create(
                company=self.company,
                name="Santander",
            )

    def test_duplicate_account_bank_holder_company_is_rejected(self):
        with self.assertRaises(IntegrityError):
            FinancialAccount.objects.create(
                company=self.company,
                bank=self.bank,
                holder=self.company_user,
                initial_balance=Decimal("200.00"),
            )
