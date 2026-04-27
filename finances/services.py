import hashlib
import re
import uuid
from calendar import monthrange
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import models, transaction
from django.utils import timezone

from finances.ai_categorization import suggest_category_for_transaction
from finances.models import (
    FinancialMovement,
    FinancialTransfer,
    BankStatementImport,
)

# =========================================
# ENCODING
# =========================================


def decode_file_content(file_content):
    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]

    for encoding in encodings:
        try:
            return file_content.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError("Unable to decode file.")


# =========================================
# DATE HELPERS
# =========================================


def get_month_start_and_end(year, month):
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


# =========================================
# BALANCE (CORRIGIDO)
# =========================================


def calculate_account_projected_balance_until(account, end_date):
    """
    Used for current/future months (projection).
    """
    movements = FinancialMovement.objects.filter(
        account=account,
        due_date__lte=end_date,
        status__in=[
            FinancialMovement.MovementStatus.PAID,
            FinancialMovement.MovementStatus.PENDING,
            FinancialMovement.MovementStatus.OVERDUE,
        ],
    )

    balance = account.initial_balance

    for m in movements:
        balance += m.signed_amount

    return balance


def calculate_account_real_balance_until(account, end_date):
    """
    Used for past months (real balance only).
    """
    movements = FinancialMovement.objects.filter(
        account=account,
        paid_at__isnull=False,
        paid_at__lte=end_date,
        status=FinancialMovement.MovementStatus.PAID,
    )

    balance = account.initial_balance

    for m in movements:
        balance += m.signed_amount

    return balance


def calculate_account_month_summary(account, year, month):
    month_start, month_end = get_month_start_and_end(year, month)

    today = timezone.localdate()
    current_month_start = today.replace(day=1)

    previous_day = month_start - relativedelta(days=1)

    is_past_month = month_start < current_month_start

    if is_past_month:
        initial_balance = calculate_account_real_balance_until(account, previous_day)
    else:
        initial_balance = calculate_account_projected_balance_until(
            account, previous_day
        )

    paid_movements = FinancialMovement.objects.filter(
        account=account,
        paid_at__isnull=False,
        paid_at__gte=month_start,
        paid_at__lte=month_end,
        status=FinancialMovement.MovementStatus.PAID,
    )

    open_movements = FinancialMovement.objects.filter(
        account=account,
        paid_at__isnull=True,
        due_date__gte=month_start,
        due_date__lte=month_end,
        status__in=[
            FinancialMovement.MovementStatus.PENDING,
            FinancialMovement.MovementStatus.OVERDUE,
        ],
    )

    current_balance = initial_balance

    for m in paid_movements:
        current_balance += m.signed_amount

    expected_balance = current_balance

    for m in open_movements:
        expected_balance += m.signed_amount

    return {
        "initial_balance": initial_balance,
        "current_balance": current_balance,
        "expected_balance": expected_balance,
    }


# =========================================
# DISPLAY
# =========================================


def get_movements_for_display_month(company, year, month, account=None):
    month_start, month_end = get_month_start_and_end(year, month)

    queryset = FinancialMovement.objects.filter(company=company)

    if account:
        queryset = queryset.filter(account=account)

    return queryset.filter(
        models.Q(
            paid_at__isnull=False,
            paid_at__gte=month_start,
            paid_at__lte=month_end,
        )
        | models.Q(
            paid_at__isnull=True,
            due_date__gte=month_start,
            due_date__lte=month_end,
        )
    ).order_by("-paid_at", "-due_date", "-id")


# =========================================
# MARK AS PAID
# =========================================


@transaction.atomic
def mark_movement_as_paid(movement, payment_comment=""):
    movement.status = FinancialMovement.MovementStatus.PAID
    movement.paid_at = timezone.localdate()
    movement.payment_comment = payment_comment or ""
    movement.save()
    return movement


# =========================================
# CREATION
# =========================================


def get_manual_movement_initial_status(due_date):
    if due_date < timezone.localdate():
        return FinancialMovement.MovementStatus.OVERDUE
    return FinancialMovement.MovementStatus.PENDING


@transaction.atomic
def create_single_movement(
    company,
    account,
    movement_type,
    amount,
    due_date,
    description="",
    category=None,
    subcategory=None,
):
    """
    Create a single financial movement.
    """
    return FinancialMovement.objects.create(
        company=company,
        account=account,
        movement_type=movement_type,
        category=category,
        subcategory=subcategory,
        recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
        description=description,
        amount=amount,
        due_date=due_date,
        status=get_manual_movement_initial_status(due_date),
    )


@transaction.atomic
def create_installment_movements(
    company,
    account,
    movement_type,
    amount,
    due_date,
    installments,
    amount_mode,
    description="",
    category=None,
    subcategory=None,
):
    """
    Create installment movements.
    """
    group = str(uuid.uuid4())

    if amount_mode == "TOTAL":
        installment_amount = amount / Decimal(installments)
    else:
        installment_amount = amount

    movements = []

    for index in range(installments):
        installment_due_date = due_date + relativedelta(months=index)

        movement = FinancialMovement.objects.create(
            company=company,
            account=account,
            movement_type=movement_type,
            category=category,
            subcategory=subcategory,
            recurrence_type=FinancialMovement.RecurrenceType.INSTALLMENT,
            description=description,
            amount=installment_amount,
            due_date=installment_due_date,
            status=get_manual_movement_initial_status(installment_due_date),
            installment_group=group,
            installment_number=index + 1,
            installment_total=installments,
        )

        movements.append(movement)

    return movements


@transaction.atomic
def create_transfer(
    company, origin_account, destination_account, amount, due_date, description=""
):
    """
    Create a transfer between two accounts.
    """
    status = get_manual_movement_initial_status(due_date)

    origin_movement = FinancialMovement.objects.create(
        company=company,
        account=origin_account,
        movement_type=FinancialMovement.MovementType.EXPENSE,
        recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
        description=description or "Transferência enviada",
        amount=amount,
        due_date=due_date,
        status=status,
    )

    destination_movement = FinancialMovement.objects.create(
        company=company,
        account=destination_account,
        movement_type=FinancialMovement.MovementType.INCOME,
        recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
        description=description or "Transferência recebida",
        amount=amount,
        due_date=due_date,
        status=status,
    )

    return FinancialTransfer.objects.create(
        company=company,
        origin_account=origin_account,
        destination_account=destination_account,
        amount=amount,
        due_date=due_date,
        description=description,
        origin_movement=origin_movement,
        destination_movement=destination_movement,
    )


@transaction.atomic
def update_overdue_financial_movements():
    """
    Update pending movements to overdue.
    """
    today = timezone.localdate()

    return FinancialMovement.objects.filter(
        status=FinancialMovement.MovementStatus.PENDING,
        due_date__lt=today,
    ).update(
        status=FinancialMovement.MovementStatus.OVERDUE,
    )


# =========================================
# IMPORT HELPERS (CORRIGIDO)
# =========================================


def build_statement_reference(account, movement_date, description, amount, line_number):
    raw = f"{account.id}|{movement_date}|{description}|{amount}|{line_number}"
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_santander_amount(raw):
    sign = raw[0]
    digits = raw[1:]
    value = Decimal(digits) / Decimal("100")
    if sign == "-":
        value *= -1
    return value


def parse_santander_positional_line(line):
    line = line.strip()

    if not line.startswith("030"):
        return None

    signed_values = re.findall(r"[+-]\d{18}", line)
    if not signed_values:
        return None

    amount = parse_santander_amount(signed_values[-1])

    dates = []
    for match in re.finditer(r"20\d{6}", line):
        try:
            d = date(
                int(match.group()[0:4]),
                int(match.group()[4:6]),
                int(match.group()[6:8]),
            )
            dates.append((d, match.end()))
        except ValueError:
            continue

    if not dates:
        return None

    movement_date, desc_start = dates[-1]

    next_number = re.search(r"[+-]\d{18}", line[desc_start:])
    if next_number:
        desc_end = desc_start + next_number.start()
        description = line[desc_start:desc_end].strip()
    else:
        description = line[desc_start:].strip()

    return {
        "date": movement_date,
        "description": description,
        "amount": amount,
    }


def parse_santander_positional_statement(content):
    transactions = []
    total = 0
    invalid = 0

    for i, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()

        if not line.startswith("030"):
            continue

        total += 1

        parsed = parse_santander_positional_line(line)

        if parsed:
            parsed["line_number"] = i
            parsed["raw_line"] = raw_line
            transactions.append(parsed)
        else:
            invalid += 1

    return {
        "transactions": transactions,
        "total_lines": total,
        "invalid_lines": invalid,
    }


# =========================================
# FIXED MOVEMENTS
# =========================================


def get_fixed_occurrence_due_date(template, year, month):
    """
    Return the due date for a fixed movement occurrence in a specific month.
    """
    last_day = monthrange(year, month)[1]
    day = min(template.due_date.day, last_day)

    return date(year, month, day)


@transaction.atomic
def create_fixed_movement_template(
    company,
    account,
    movement_type,
    amount,
    due_date,
    description="",
    category=None,
    subcategory=None,
):
    """
    Create a fixed movement template without end date.
    """
    return FinancialMovement.objects.create(
        company=company,
        account=account,
        movement_type=movement_type,
        category=category,
        subcategory=subcategory,
        recurrence_type=FinancialMovement.RecurrenceType.FIXED,
        description=description,
        amount=amount,
        due_date=due_date,
        status=FinancialMovement.MovementStatus.PENDING,
        fixed_group=str(uuid.uuid4()),
        is_fixed_template=True,
    )


@transaction.atomic
def ensure_fixed_movements_for_month(company, year, month):
    """
    Ensure fixed movement occurrences exist for the selected month.
    """
    month_start, month_end = get_month_start_and_end(
        year=year,
        month=month,
    )

    templates = FinancialMovement.objects.filter(
        company=company,
        recurrence_type=FinancialMovement.RecurrenceType.FIXED,
        is_fixed_template=True,
        due_date__lte=month_end,
    )

    created_movements = []

    for template in templates:
        occurrence_month = date(year, month, 1)

        exists = FinancialMovement.objects.filter(
            parent_fixed_movement=template,
            fixed_occurrence_month=occurrence_month,
        ).exists()

        if exists:
            continue

        occurrence_due_date = get_fixed_occurrence_due_date(
            template=template,
            year=year,
            month=month,
        )

        movement = FinancialMovement.objects.create(
            company=company,
            account=template.account,
            movement_type=template.movement_type,
            recurrence_type=FinancialMovement.RecurrenceType.FIXED,
            description=template.description,
            amount=template.amount,
            due_date=occurrence_due_date,
            status=get_manual_movement_initial_status(occurrence_due_date),
            fixed_group=template.fixed_group,
            is_fixed_template=False,
            parent_fixed_movement=template,
            fixed_occurrence_month=occurrence_month,
        )

        created_movements.append(movement)

    return created_movements


def parse_csv_statement(content):
    """
    Parse CSV statement with expected columns:
    data, descricao, montante, saldo.
    """
    csv_file = io.StringIO(content)
    reader = csv.DictReader(csv_file, delimiter=";")

    transactions = []
    total = 0
    invalid = 0

    if not reader.fieldnames:
        return {
            "transactions": transactions,
            "total_lines": total,
            "invalid_lines": invalid,
        }

    reader.fieldnames = [
        field.strip().lower()
        for field in reader.fieldnames
    ]

    for line_number, row in enumerate(reader, start=2):
        total += 1

        raw_date = row.get("data")
        raw_description = row.get("descricao") or row.get("descrição") or ""
        raw_amount = row.get("montante")

        if not raw_date or not raw_amount:
            invalid += 1
            continue

        try:
            day, month, year = raw_date.strip().split("/")

            movement_date = date(
                int(year),
                int(month),
                int(day),
            )

            amount = Decimal(
                raw_amount.strip().replace(".", "").replace(",", ".")
            )
        except (ValueError, TypeError):
            invalid += 1
            continue

        transactions.append(
            {
                "date": movement_date,
                "description": raw_description.strip(),
                "amount": amount,
                "line_number": line_number,
                "raw_line": str(row),
            }
        )

    return {
        "transactions": transactions,
        "total_lines": total,
        "invalid_lines": invalid,
    }


def parse_bank_statement(content):
    """
    Parse supported bank statement formats.
    """
    stripped_content = content.lstrip()

    if stripped_content.startswith("010") or stripped_content.startswith("030"):
        return parse_santander_positional_statement(content)

    return parse_csv_statement(content)


# =========================================
# IMPORT MAIN
# =========================================

def find_matching_manual_movement(company, account, movement_type, amount, movement_date):
    """
    Find a compatible pending or overdue manual movement for bank reconciliation.
    """
    return (
        FinancialMovement.objects
        .filter(
            company=company,
            account=account,
            movement_type=movement_type,
            amount=amount,
            status__in=[
                FinancialMovement.MovementStatus.PENDING,
                FinancialMovement.MovementStatus.OVERDUE,
            ],
            is_imported=False,
            paid_at__isnull=True,
            due_date__lte=movement_date,
        )
        .order_by(
            "-due_date",
            "-id",
        )
        .first()
    )

@transaction.atomic
def import_santander_portugal_consolidated_statement(company, account, file_content):
    """
    Import Santander Portugal consolidated statement.

    This function:
    - parses Santander TXT or supported CSV files;
    - detects income or expense using the signed amount;
    - prevents duplicated imported movements;
    - tries to match pending/overdue manual movements;
    - suggests category/subcategory using local rules or AI;
    - saves categorization suggestion into the movement and audit row;
    - never blocks the import if categorization fails.
    """
    decoded_content = decode_file_content(file_content)

    parsed = parse_bank_statement(decoded_content) or {
        "transactions": [],
        "total_lines": 0,
        "invalid_lines": 0,
    }

    transactions = parsed["transactions"]
    total_lines = parsed["total_lines"]
    invalid_lines = parsed["invalid_lines"]

    imported = 0
    matched = 0
    skipped = 0

    for transaction in transactions:
        movement_date = transaction["date"]
        description = transaction["description"]
        signed_amount = transaction["amount"]

        if signed_amount >= 0:
            movement_type = FinancialMovement.MovementType.INCOME
        else:
            movement_type = FinancialMovement.MovementType.EXPENSE

        movement_amount = abs(signed_amount)

        line_number = transaction.get("line_number", 0)
        raw_line = transaction.get("raw_line", "")

        external_reference = build_statement_reference(
            account=account,
            movement_date=movement_date,
            description=description,
            amount=signed_amount,
            line_number=line_number,
        )

        suggestion = suggest_category_for_transaction(
            company=company,
            description=description,
            movement_type=movement_type,
            amount=movement_amount,
        )

        suggested_category = suggestion.category if suggestion else None
        suggested_subcategory = suggestion.subcategory if suggestion else None
        categorization_confidence = suggestion.confidence if suggestion else None
        categorization_source = suggestion.source if suggestion else ""
        categorization_reason = suggestion.reason if suggestion else ""

        already_exists = FinancialMovement.objects.filter(
            company=company,
            account=account,
            external_reference=external_reference,
        ).exists()

        if already_exists:
            skipped += 1

            BankStatementImport.objects.create(
                company=company,
                account=account,
                date=movement_date,
                description=description,
                amount=signed_amount,
                external_reference=external_reference,
                status=BankStatementImport.ImportStatus.DUPLICATED,
                raw_line=raw_line,
                suggested_category=suggested_category,
                suggested_subcategory=suggested_subcategory,
                categorization_confidence=categorization_confidence,
                categorization_source=categorization_source,
                categorization_reason=categorization_reason,
            )

            continue

        matched_movement = find_matching_manual_movement(
            company=company,
            account=account,
            movement_type=movement_type,
            amount=movement_amount,
            movement_date=movement_date,
        )

        if matched_movement:
            matched_movement.status = FinancialMovement.MovementStatus.PAID
            matched_movement.paid_at = movement_date
            matched_movement.payment_comment = (
                "Conciliado automaticamente por importação Santander."
            )
            matched_movement.external_reference = external_reference
            matched_movement.is_reconciled = True

            if suggested_category and not matched_movement.category:
                matched_movement.category = suggested_category

            if suggested_subcategory and not matched_movement.subcategory:
                matched_movement.subcategory = suggested_subcategory

            matched_movement.save(
                update_fields=[
                    "status",
                    "paid_at",
                    "payment_comment",
                    "external_reference",
                    "is_reconciled",
                    "category",
                    "subcategory",
                    "updated_at",
                ]
            )

            BankStatementImport.objects.create(
                company=company,
                account=account,
                movement=matched_movement,
                date=movement_date,
                description=description,
                amount=signed_amount,
                external_reference=external_reference,
                status=BankStatementImport.ImportStatus.MATCHED,
                raw_line=raw_line,
                suggested_category=suggested_category,
                suggested_subcategory=suggested_subcategory,
                categorization_confidence=categorization_confidence,
                categorization_source=categorization_source,
                categorization_reason=categorization_reason,
            )

            matched += 1
            continue

        movement = FinancialMovement.objects.create(
            company=company,
            account=account,
            movement_type=movement_type,
            category=suggested_category,
            subcategory=suggested_subcategory,
            recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
            description=description,
            amount=movement_amount,
            due_date=movement_date,
            paid_at=movement_date,
            status=FinancialMovement.MovementStatus.PAID,
            is_imported=True,
            is_reconciled=True,
            external_reference=external_reference,
        )

        BankStatementImport.objects.create(
            company=company,
            account=account,
            movement=movement,
            date=movement_date,
            description=description,
            amount=signed_amount,
            external_reference=external_reference,
            status=BankStatementImport.ImportStatus.IMPORTED,
            raw_line=raw_line,
            suggested_category=suggested_category,
            suggested_subcategory=suggested_subcategory,
            categorization_confidence=categorization_confidence,
            categorization_source=categorization_source,
            categorization_reason=categorization_reason,
        )

        imported += 1

    return {
        "total_lines": total_lines,
        "valid_transactions": len(transactions),
        "invalid_lines": invalid_lines,
        "imported_count": imported,
        "matched_count": matched,
        "skipped_count": skipped,
    }