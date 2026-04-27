from django.db import transaction

from finances.ai_categorization import suggest_category_for_transaction
from finances.models import BankStatementImport, FinancialMovement
from finances.services.reconciliation_service import (
    build_statement_reference,
    find_matching_manual_movement,
)
from finances.services.statement_parser_service import (
    decode_file_content,
    parse_bank_statement,
)


def get_movement_type_from_signed_amount(signed_amount):
    """
    Return movement type based on signed bank statement amount.
    """
    if signed_amount >= 0:
        return FinancialMovement.MovementType.INCOME

    return FinancialMovement.MovementType.EXPENSE


def create_duplicate_import_audit(
    company,
    account,
    movement_date,
    description,
    signed_amount,
    external_reference,
    raw_line,
    suggested_category,
    suggested_subcategory,
    categorization_confidence,
    categorization_source,
    categorization_reason,
):
    """
    Create audit row for duplicated imported statement transaction.
    """
    return BankStatementImport.objects.create(
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


def reconcile_existing_movement(
    matched_movement,
    movement_date,
    external_reference,
    suggested_category,
    suggested_subcategory,
):
    """
    Reconcile an existing manual movement with a bank statement transaction.
    """
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

    return matched_movement


def create_matched_import_audit(
    company,
    account,
    movement,
    movement_date,
    description,
    signed_amount,
    external_reference,
    raw_line,
    suggested_category,
    suggested_subcategory,
    categorization_confidence,
    categorization_source,
    categorization_reason,
):
    """
    Create audit row for a reconciled statement transaction.
    """
    return BankStatementImport.objects.create(
        company=company,
        account=account,
        movement=movement,
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


def create_imported_movement(
    company,
    account,
    movement_type,
    suggested_category,
    suggested_subcategory,
    description,
    movement_amount,
    movement_date,
    external_reference,
):
    """
    Create a new paid movement from an imported bank statement transaction.
    """
    return FinancialMovement.objects.create(
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


def create_imported_movement_audit(
    company,
    account,
    movement,
    movement_date,
    description,
    signed_amount,
    external_reference,
    raw_line,
    suggested_category,
    suggested_subcategory,
    categorization_confidence,
    categorization_source,
    categorization_reason,
):
    """
    Create audit row for a newly imported movement.
    """
    return BankStatementImport.objects.create(
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


@transaction.atomic
def import_santander_portugal_consolidated_statement(company, account, file_content):
    """
    Import Santander Portugal consolidated statement.

    This function:
    - decodes uploaded file content;
    - parses supported statement formats;
    - detects income or expense;
    - prevents duplicated imported movements;
    - reconciles compatible pending/overdue manual movements;
    - suggests category/subcategory using local rules or AI;
    - creates import audit rows.
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

        movement_type = get_movement_type_from_signed_amount(
            signed_amount=signed_amount,
        )

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

            create_duplicate_import_audit(
                company=company,
                account=account,
                movement_date=movement_date,
                description=description,
                signed_amount=signed_amount,
                external_reference=external_reference,
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
            reconciled_movement = reconcile_existing_movement(
                matched_movement=matched_movement,
                movement_date=movement_date,
                external_reference=external_reference,
                suggested_category=suggested_category,
                suggested_subcategory=suggested_subcategory,
            )

            create_matched_import_audit(
                company=company,
                account=account,
                movement=reconciled_movement,
                movement_date=movement_date,
                description=description,
                signed_amount=signed_amount,
                external_reference=external_reference,
                raw_line=raw_line,
                suggested_category=suggested_category,
                suggested_subcategory=suggested_subcategory,
                categorization_confidence=categorization_confidence,
                categorization_source=categorization_source,
                categorization_reason=categorization_reason,
            )

            matched += 1
            continue

        movement = create_imported_movement(
            company=company,
            account=account,
            movement_type=movement_type,
            suggested_category=suggested_category,
            suggested_subcategory=suggested_subcategory,
            description=description,
            movement_amount=movement_amount,
            movement_date=movement_date,
            external_reference=external_reference,
        )

        create_imported_movement_audit(
            company=company,
            account=account,
            movement=movement,
            movement_date=movement_date,
            description=description,
            signed_amount=signed_amount,
            external_reference=external_reference,
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
