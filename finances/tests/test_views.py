from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from companies.models import Company, CompanyMembership
from finances.models import (
    Bank,
    FinancialAccount,
    FinancialCategory,
    FinancialMovement,
)

User = get_user_model()


class FinanceViewsTestCase(TestCase):
    """
    Tests for finance views.
    """

    def setUp(self):
        """
        Create company, owner, employee, bank and account.
        """
        self.company_user = User.objects.create_user(
            nif="500000001",
            email="empresa@example.com",
            password="Testpass123",
            full_name="Empresa Teste",
            user_type=User.UserType.COMPANY,
        )

        self.owner_user = User.objects.create_user(
            nif="123456789",
            email="owner@example.com",
            password="Testpass123",
            full_name="Dono Responsável",
            user_type=User.UserType.PERSON,
        )

        self.employee_user = User.objects.create_user(
            nif="123456780",
            email="employee@example.com",
            password="Testpass123",
            full_name="Funcionário Teste",
            user_type=User.UserType.PERSON,
        )

        self.company = Company.objects.create(
            user=self.company_user,
            name="Empresa Teste",
            nif="500000001",
            email="empresa@example.com",
        )

        CompanyMembership.objects.create(
            company=self.company,
            person=self.owner_user,
            membership_type=CompanyMembership.MembershipType.OWNER,
        )

        CompanyMembership.objects.create(
            company=self.company,
            person=self.employee_user,
            membership_type=CompanyMembership.MembershipType.EMPLOYEE,
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

        self.category = FinancialCategory.objects.create(
            company=self.company,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            name="Despesas",
        )

    def test_finance_dashboard_requires_login(self):
        """
        Finance dashboard should redirect anonymous user to login.
        """
        response = self.client.get(
            reverse("finance_dashboard")
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_finance_dashboard_loads_for_owner(self):
        """
        Owner should access finance dashboard.
        """
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse("finance_dashboard")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Financeiro")

    def test_employee_can_view_finance_dashboard(self):
        """
        Employee can view finance dashboard.
        """
        self.client.force_login(self.employee_user)

        response = self.client.get(
            reverse("finance_dashboard")
        )

        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_create_bank(self):
        """
        Employee should not create banks.
        """
        self.client.force_login(self.employee_user)

        response = self.client.post(
            reverse("bank_create"),
            data={
                "name": "Banco Funcionário",
            },
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("finance_dashboard"),
        )

        self.assertFalse(
            Bank.objects.filter(
                company=self.company,
                name="Banco Funcionário",
            ).exists()
        )

    def test_owner_can_create_bank(self):
        """
        Owner should create bank.
        """
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("bank_create"),
            data={
                "name": "Novo Banco",
            },
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("finance_dashboard"),
        )

        self.assertTrue(
            Bank.objects.filter(
                company=self.company,
                name="Novo Banco",
            ).exists()
        )

    def test_employee_cannot_create_financial_account(self):
        """
        Employee should not create financial account.
        """
        self.client.force_login(self.employee_user)

        response = self.client.post(
            reverse("financial_account_create"),
            data={
                "bank": self.bank.id,
                "holder": self.company_user.id,
                "initial_balance": "100.00",
            },
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("finance_dashboard"),
        )

        self.assertEqual(
            FinancialAccount.objects.filter(company=self.company).count(),
            1,
        )

    def test_owner_can_create_financial_category(self):
        """
        Owner should create financial category.
        """
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("financial_category_create"),
            data={
                "movement_type": FinancialMovement.MovementType.INCOME,
                "name": "Receitas",
            },
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("finance_dashboard"),
        )

        self.assertTrue(
            FinancialCategory.objects.filter(
                company=self.company,
                name="Receitas",
            ).exists()
        )

    def test_employee_cannot_create_financial_category(self):
        """
        Employee should not create financial category.
        """
        self.client.force_login(self.employee_user)

        response = self.client.post(
            reverse("financial_category_create"),
            data={
                "movement_type": FinancialMovement.MovementType.INCOME,
                "name": "Receitas Funcionário",
            },
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("finance_dashboard"),
        )

        self.assertFalse(
            FinancialCategory.objects.filter(
                company=self.company,
                name="Receitas Funcionário",
            ).exists()
        )

    def test_owner_can_create_single_movement(self):
        """
        Owner should create a single movement.
        """
        self.client.force_login(self.owner_user)

        response = self.client.post(
            reverse("financial_movement_create"),
            data={
                "account": self.account.id,
                "movement_type": FinancialMovement.MovementType.EXPENSE,
                "recurrence_type": FinancialMovement.RecurrenceType.SINGLE,
                "category": self.category.id,
                "amount": "50.00",
                "due_date": "2026-01-10",
                "description": "Despesa teste",
            },
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("finance_dashboard"),
        )

        self.assertTrue(
            FinancialMovement.objects.filter(
                company=self.company,
                description="Despesa teste",
                amount=Decimal("50.00"),
            ).exists()
        )

    def test_employee_cannot_create_single_movement(self):
        """
        Employee should not create movement.
        """
        self.client.force_login(self.employee_user)

        response = self.client.post(
            reverse("financial_movement_create"),
            data={
                "account": self.account.id,
                "movement_type": FinancialMovement.MovementType.EXPENSE,
                "recurrence_type": FinancialMovement.RecurrenceType.SINGLE,
                "category": self.category.id,
                "amount": "50.00",
                "due_date": "2026-01-10",
                "description": "Despesa funcionário",
            },
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("finance_dashboard"),
        )

        self.assertFalse(
            FinancialMovement.objects.filter(
                company=self.company,
                description="Despesa funcionário",
            ).exists()
        )

    def test_account_detail_loads_for_owner(self):
        """
        Account detail should load.
        """
        self.client.force_login(self.owner_user)

        response = self.client.get(
            reverse(
                "financial_account_detail",
                kwargs={
                    "account_id": self.account.id,
                },
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_import_page_requires_owner(self):
        """
        Employee should not access import page.
        """
        self.client.force_login(self.employee_user)

        response = self.client.get(
            reverse("bank_statement_import"),
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("finance_dashboard"),
        )