from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from companies.models import Company
from finances.models import Bank, FinancialAccount, FinancialMovement, FinancialTransfer
from finances.services import (
    build_statement_reference,
    calculate_account_month_summary,
    create_installment_movements,
    create_single_movement,
    create_transfer,
    ensure_fixed_movements_for_month,
    get_manual_movement_initial_status,
    import_santander_portugal_consolidated_statement,
    parse_santander_amount,
    parse_santander_positional_line,
    parse_santander_positional_statement,
)

User = get_user_model()


class FinanceServiceTestCase(TestCase):
    """
    Tests for finance service rules.
    """

    def setUp(self):
        """
        Create base company, users, bank and accounts.
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

        self.destination_account = FinancialAccount.objects.create(
            company=self.company,
            bank=self.bank,
            holder=self.person_user,
            initial_balance=Decimal("0.00"),
        )

    def test_manual_movement_initial_status_pending_for_today_or_future(self):
        """
        Movement due today or in the future should start as pending.
        """
        today = timezone.localdate()

        status = get_manual_movement_initial_status(today)

        self.assertEqual(
            status,
            FinancialMovement.MovementStatus.PENDING,
        )

    def test_manual_movement_initial_status_overdue_for_past_date(self):
        """
        Movement due before today should start as overdue.
        """
        yesterday = timezone.localdate() - timezone.timedelta(days=1)

        status = get_manual_movement_initial_status(yesterday)

        self.assertEqual(
            status,
            FinancialMovement.MovementStatus.OVERDUE,
        )

    def test_create_single_income_movement(self):
        """
        Single income movement should be created correctly.
        """
        movement = create_single_movement(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.INCOME,
            amount=Decimal("150.00"),
            due_date=timezone.localdate(),
            description="Receita teste",
        )

        self.assertEqual(movement.company, self.company)
        self.assertEqual(movement.account, self.account)
        self.assertEqual(movement.amount, Decimal("150.00"))
        self.assertEqual(movement.movement_type, FinancialMovement.MovementType.INCOME)

    def test_create_single_expense_movement_signed_amount(self):
        """
        Expense signed amount should be negative.
        """
        movement = create_single_movement(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            amount=Decimal("50.00"),
            due_date=timezone.localdate(),
            description="Despesa teste",
        )

        self.assertEqual(
            movement.signed_amount,
            Decimal("-50.00"),
        )

    def test_create_installment_movements_with_total_amount(self):
        """
        Total amount should be divided by installments.
        """
        movements = create_installment_movements(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            amount=Decimal("300.00"),
            due_date=date(2026, 1, 10),
            installments=3,
            amount_mode="TOTAL",
            description="Compra parcelada",
        )

        self.assertEqual(len(movements), 3)
        self.assertEqual(movements[0].amount, Decimal("100.00"))
        self.assertEqual(movements[1].amount, Decimal("100.00"))
        self.assertEqual(movements[2].amount, Decimal("100.00"))
        self.assertEqual(movements[0].installment_number, 1)
        self.assertEqual(movements[2].installment_number, 3)

    def test_create_installment_movements_with_installment_amount(self):
        """
        Installment amount should be repeated for each installment.
        """
        movements = create_installment_movements(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            amount=Decimal("100.00"),
            due_date=date(2026, 1, 10),
            installments=3,
            amount_mode="INSTALLMENT",
            description="Compra parcelada",
        )

        self.assertEqual(len(movements), 3)
        self.assertEqual(movements[0].amount, Decimal("100.00"))
        self.assertEqual(movements[1].amount, Decimal("100.00"))
        self.assertEqual(movements[2].amount, Decimal("100.00"))

    def test_create_transfer_creates_two_movements(self):
        """
        Transfer should create one expense and one income movement.
        """
        transfer = create_transfer(
            company=self.company,
            origin_account=self.account,
            destination_account=self.destination_account,
            amount=Decimal("200.00"),
            due_date=timezone.localdate(),
            description="Transferência teste",
        )

        self.assertIsInstance(transfer, FinancialTransfer)
        self.assertEqual(
            transfer.origin_movement.movement_type,
            FinancialMovement.MovementType.EXPENSE,
        )
        self.assertEqual(
            transfer.destination_movement.movement_type,
            FinancialMovement.MovementType.INCOME,
        )
        self.assertEqual(transfer.origin_movement.amount, Decimal("200.00"))
        self.assertEqual(transfer.destination_movement.amount, Decimal("200.00"))

    def test_fixed_movement_generates_month_occurrence(self):
        """
        Fixed movement template should generate one occurrence for selected month.
        """
        template = FinancialMovement.objects.create(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            recurrence_type=FinancialMovement.RecurrenceType.FIXED,
            description="Aluguel",
            amount=Decimal("500.00"),
            due_date=date(2026, 1, 31),
            status=FinancialMovement.MovementStatus.PENDING,
            is_fixed_template=True,
        )

        created = ensure_fixed_movements_for_month(
            company=self.company,
            year=2026,
            month=2,
        )

        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].parent_fixed_movement, template)
        self.assertEqual(created[0].due_date, date(2026, 2, 28))

    def test_fixed_movement_does_not_duplicate_occurrence(self):
        """
        Fixed movement occurrence should not be duplicated for same month.
        """
        FinancialMovement.objects.create(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            recurrence_type=FinancialMovement.RecurrenceType.FIXED,
            description="Aluguel",
            amount=Decimal("500.00"),
            due_date=date(2026, 1, 10),
            status=FinancialMovement.MovementStatus.PENDING,
            is_fixed_template=True,
        )

        ensure_fixed_movements_for_month(self.company, 2026, 2)
        ensure_fixed_movements_for_month(self.company, 2026, 2)

        count = FinancialMovement.objects.filter(
            company=self.company,
            recurrence_type=FinancialMovement.RecurrenceType.FIXED,
            is_fixed_template=False,
            fixed_occurrence_month=date(2026, 2, 1),
        ).count()

        self.assertEqual(count, 1)

    def test_parse_santander_amount_positive(self):
        """
        Santander positive amount should be parsed as positive decimal.
        """
        amount = parse_santander_amount("+000000000000004225")

        self.assertEqual(
            amount,
            Decimal("42.25"),
        )

    def test_parse_santander_amount_negative(self):
        """
        Santander negative amount should be parsed as negative decimal.
        """
        amount = parse_santander_amount("-000000000000001590")

        self.assertEqual(
            amount,
            Decimal("-15.90"),
        )

    def test_parse_santander_positional_expense_line(self):
        """
        Santander expense line should parse date, description and amount.
        """
        line = (
            "0300018    000003EUR  00066248782020  20250805  "
            "20250805COMISS„O DE GEST„O                       "
            "00000000    +000000000000000000 -000000000000001590 "
            "000000000000000"
        )

        parsed = parse_santander_positional_line(line)

        self.assertEqual(parsed["date"], date(2025, 8, 5))
        self.assertIn("COMISS", parsed["description"])
        self.assertEqual(parsed["amount"], Decimal("-15.90"))

    def test_parse_santander_positional_income_line(self):
        """
        Santander income line should parse positive transaction amount.
        """
        line = (
            "0300018 4TF000003EUR  000662487820200920250805  "
            "20250805TRANSF CESAR BERBEL LEME DE AL           "
            "00000000    +000000000000000000 +000000000000004225 "
            "000000000000000"
        )

        parsed = parse_santander_positional_line(line)

        self.assertEqual(parsed["date"], date(2025, 8, 5))
        self.assertIn("TRANSF CESAR", parsed["description"])
        self.assertEqual(parsed["amount"], Decimal("42.25"))

    def test_parse_santander_positional_statement_counts_lines(self):
        """
        Statement parser should count valid transaction lines.
        """
        content = "\n".join(
            [
                "0100018    000003EUR  00066248782020  20250805  20250805",
                "0300018    000003EUR  00066248782020  20250805  20250805COMISS„O DE GEST„O                       00000000    +000000000000000000 -000000000000001590 000000000000000",
                "0300018 4TF000003EUR  000662487820200920250805  20250805TRANSF CESAR BERBEL LEME DE AL           00000000    +000000000000000000 +000000000000004225 000000000000000",
                "0700018    000003EUR  00066248782020  20260427  20260427",
            ]
        )

        parsed = parse_santander_positional_statement(content)

        self.assertEqual(parsed["total_lines"], 2)
        self.assertEqual(parsed["invalid_lines"], 0)
        self.assertEqual(len(parsed["transactions"]), 2)

    def test_import_santander_statement_creates_income_and_expense(self):
        """
        Import should create income and expense movements with correct values.
        """
        content = "\n".join(
            [
                "0300018    000003EUR  00066248782020  20250805  20250805COMISS„O DE GEST„O                       00000000    +000000000000000000 -000000000000001590 000000000000000",
                "0300018 4TF000003EUR  000662487820200920250805  20250805TRANSF CESAR BERBEL LEME DE AL           00000000    +000000000000000000 +000000000000004225 000000000000000",
            ]
        )

        result = import_santander_portugal_consolidated_statement(
            company=self.company,
            account=self.account,
            file_content=content.encode("cp1252"),
        )

        self.assertEqual(result["total_lines"], 2)
        self.assertEqual(result["valid_transactions"], 2)
        self.assertEqual(result["imported_count"], 2)

        income_count = FinancialMovement.objects.filter(
            company=self.company,
            movement_type=FinancialMovement.MovementType.INCOME,
            amount=Decimal("42.25"),
        ).count()

        expense_count = FinancialMovement.objects.filter(
            company=self.company,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            amount=Decimal("15.90"),
        ).count()

        self.assertEqual(income_count, 1)
        self.assertEqual(expense_count, 1)

    def test_import_santander_statement_avoids_duplicate_import(self):
        """
        Reimporting same content should skip duplicated movements.
        """
        content = (
            "0300018    000003EUR  00066248782020  20250805  "
            "20250805COMISS„O DE GEST„O                       "
            "00000000    +000000000000000000 -000000000000001590 "
            "000000000000000"
        )

        import_santander_portugal_consolidated_statement(
            company=self.company,
            account=self.account,
            file_content=content.encode("cp1252"),
        )

        result = import_santander_portugal_consolidated_statement(
            company=self.company,
            account=self.account,
            file_content=content.encode("cp1252"),
        )

        self.assertEqual(result["imported_count"], 0)
        self.assertEqual(result["skipped_count"], 1)

    def test_past_month_balance_uses_paid_movements_only(self):
        """
        Past month initial balance should use only paid movements before the month.
        """
        FinancialMovement.objects.create(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.INCOME,
            recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
            amount=Decimal("500.00"),
            due_date=date(2025, 8, 10),
            paid_at=date(2025, 8, 10),
            status=FinancialMovement.MovementStatus.PAID,
        )

        FinancialMovement.objects.create(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
            amount=Decimal("100.00"),
            due_date=date(2025, 8, 15),
            status=FinancialMovement.MovementStatus.PENDING,
        )

        summary = calculate_account_month_summary(
            account=self.account,
            year=2025,
            month=9,
        )

        self.assertEqual(
            summary["initial_balance"],
            Decimal("1500.00"),
        )

    def test_month_summary_expected_includes_open_movements(self):
        """
        Expected balance should include pending movements in selected month.
        """
        FinancialMovement.objects.create(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.INCOME,
            recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
            amount=Decimal("500.00"),
            due_date=date(2025, 8, 10),
            paid_at=date(2025, 8, 10),
            status=FinancialMovement.MovementStatus.PAID,
        )

        FinancialMovement.objects.create(
            company=self.company,
            account=self.account,
            movement_type=FinancialMovement.MovementType.EXPENSE,
            recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
            amount=Decimal("100.00"),
            due_date=date(2025, 8, 15),
            status=FinancialMovement.MovementStatus.PENDING,
        )

        summary = calculate_account_month_summary(
            account=self.account,
            year=2025,
            month=8,
        )

        self.assertEqual(
            summary["current_balance"],
            Decimal("1500.00"),
        )

        self.assertEqual(
            summary["expected_balance"],
            Decimal("1400.00"),
        )
