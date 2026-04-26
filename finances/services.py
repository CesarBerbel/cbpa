import csv
import hashlib
import io
import re
import uuid
from calendar import monthrange
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import models, transaction
from django.utils import timezone

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
        initial_balance = calculate_account_real_balance_until(
            account, previous_day
        )
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
        |
        models.Q(
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
def create_transfer(company, origin_account, destination_account, amount, due_date, description=""):
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
        except:
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


# =========================================
# IMPORT MAIN
# =========================================

@transaction.atomic
def import_santander_portugal_consolidated_statement(company, account, file_content):
    decoded = decode_file_content(file_content)

    parsed = parse_santander_positional_statement(decoded)

    transactions = parsed["transactions"]

    imported = 0
    skipped = 0

    for t in transactions:
        amount = t["amount"]
        movement_type = (
            FinancialMovement.MovementType.INCOME
            if amount >= 0
            else FinancialMovement.MovementType.EXPENSE
        )

        ref = build_statement_reference(
            account,
            t["date"],
            t["description"],
            amount,
            t["line_number"],
        )

        if FinancialMovement.objects.filter(
            company=company,
            account=account,
            external_reference=ref,
        ).exists():
            skipped += 1

            BankStatementImport.objects.create(
                company=company,
                account=account,
                date=t["date"],
                description=t["description"],
                amount=amount,
                external_reference=ref,
                status=BankStatementImport.ImportStatus.DUPLICATED,
                raw_line=t.get("raw_line", ""),
            )

            continue

        movement = FinancialMovement.objects.create(
            company=company,
            account=account,
            movement_type=movement_type,
            recurrence_type=FinancialMovement.RecurrenceType.SINGLE,
            description=t["description"],
            amount=abs(amount),
            due_date=t["date"],
            paid_at=t["date"],
            status=FinancialMovement.MovementStatus.PAID,
            is_imported=True,
            is_reconciled=True,
            external_reference=ref,
        )

        BankStatementImport.objects.create(
            company=company,
            account=account,
            movement=movement,
            date=t["date"],
            description=t["description"],
            amount=amount,
            external_reference=ref,
            status=BankStatementImport.ImportStatus.IMPORTED,
            raw_line=t.get("raw_line", ""),
        )

        imported += 1

    return {
        "total_lines": parsed["total_lines"],
        "valid_transactions": len(transactions),
        "invalid_lines": parsed["invalid_lines"],
        "imported_count": imported,
        "skipped_count": skipped,
    }