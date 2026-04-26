from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from companies.models import Company
from finances.models import (
    Bank,
    BankStatementImport,
    FinancialAccount,
    FinancialMovement,
)
from finances.services import import_santander_portugal_consolidated_statement

User = get_user_model()


class SantanderImportTestCase(TestCase):
    """
    Tests using real Santander Portugal consolidated TXT statement.
    """

    def setUp(self):
        """
        Create company, bank and account.
        """
        self.company_user = User.objects.create_user(
            nif="500000001",
            email="empresa@example.com",
            password="Testpass123",
            full_name="Empresa Teste",
            user_type=User.UserType.COMPANY,
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
            initial_balance=Decimal("0.00"),
        )

        self.fixture_path = (
            Path(__file__).resolve().parent / "fixtures" / "246__consolidado.txt"
        )

    def test_fixture_file_exists(self):
        """
        Real Santander fixture file must exist.
        """
        self.assertTrue(
            self.fixture_path.exists(),
            f"Fixture not found: {self.fixture_path}",
        )

    def test_import_real_santander_file_counts_transactions(self):
        """
        Import should process all transaction lines from real Santander file.
        """
        file_content = self.fixture_path.read_bytes()

        result = import_santander_portugal_consolidated_statement(
            company=self.company,
            account=self.account,
            file_content=file_content,
        )

        self.assertEqual(result["total_lines"], 178)
        self.assertEqual(result["valid_transactions"], 178)
        self.assertEqual(result["invalid_lines"], 0)
        self.assertEqual(result["imported_count"], 178)

    def test_import_real_santander_file_creates_income_and_expense(self):
        """
        Import should create both income and expense movements.
        """
        file_content = self.fixture_path.read_bytes()

        import_santander_portugal_consolidated_statement(
            company=self.company,
            account=self.account,
            file_content=file_content,
        )

        income_count = FinancialMovement.objects.filter(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.INCOME,
            is_imported=True,
        ).count()

        expense_count = FinancialMovement.objects.filter(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            is_imported=True,
        ).count()

        self.assertGreater(income_count, 0)
        self.assertGreater(expense_count, 0)

    def test_import_real_santander_file_does_not_create_zero_values(self):
        """
        Imported movements must not have zero amount.
        """
        file_content = self.fixture_path.read_bytes()

        import_santander_portugal_consolidated_statement(
            company=self.company,
            account=self.account,
            file_content=file_content,
        )

        zero_count = FinancialMovement.objects.filter(
            company=self.company,
            account=self.account,
            amount=Decimal("0.00"),
            is_imported=True,
        ).count()

        self.assertEqual(zero_count, 0)

    def test_import_real_santander_file_creates_audit_rows(self):
        """
        Every imported transaction should create an audit row.
        """
        file_content = self.fixture_path.read_bytes()

        import_santander_portugal_consolidated_statement(
            company=self.company,
            account=self.account,
            file_content=file_content,
        )

        audit_count = BankStatementImport.objects.filter(
            company=self.company,
            account=self.account,
        ).count()

        self.assertEqual(audit_count, 178)

    def test_import_real_santander_file_is_idempotent(self):
        """
        Reimporting the same file should not duplicate movements.
        """
        file_content = self.fixture_path.read_bytes()

        first_result = import_santander_portugal_consolidated_statement(
            company=self.company,
            account=self.account,
            file_content=file_content,
        )

        second_result = import_santander_portugal_consolidated_statement(
            company=self.company,
            account=self.account,
            file_content=file_content,
        )

        movement_count = FinancialMovement.objects.filter(
            company=self.company,
            account=self.account,
            is_imported=True,
        ).count()

        self.assertEqual(first_result["imported_count"], 178)
        self.assertEqual(second_result["imported_count"], 0)
        self.assertEqual(second_result["skipped_count"], 178)
        self.assertEqual(movement_count, 178)

    def test_known_santander_values_are_imported_correctly(self):
        """
        Known rows from real statement should be imported with correct values.
        """
        file_content = self.fixture_path.read_bytes()

        import_santander_portugal_consolidated_statement(
            company=self.company,
            account=self.account,
            file_content=file_content,
        )

        commission = FinancialMovement.objects.filter(
            company=self.company,
            account=self.account,
            description__icontains="GEST",
            amount=Decimal("15.90"),
            movement_type=FinancialMovement.MovementType.EXPENSE,
        ).first()

        transfer_income = FinancialMovement.objects.filter(
            company=self.company,
            account=self.account,
            description__icontains="TRANSF CESAR",
            amount=Decimal("42.25"),
            movement_type=FinancialMovement.MovementType.INCOME,
        ).first()

        self.assertIsNotNone(commission)
        self.assertIsNotNone(transfer_income)
