import uuid
from datetime import date
from dateutil.relativedelta import relativedelta

from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404

from companies.services import get_user_company, user_is_company_owner
from finances.forms import (
    BankForm,
    BankStatementImportForm,
    FinancialAccountForm,
    FinancialCategoryForm,
    FinancialMovementForm,
    FinancialSubcategoryForm,
    FinancialTransferForm,
    MarkMovementAsPaidForm,
)
from finances.models import (
    Bank,
    BankStatementImport,
    FinancialAccount,
    FinancialMovement,
)
from finances.services import (
    calculate_account_month_summary,
    create_installment_movements,
    create_single_movement,
    create_transfer,
    ensure_fixed_movements_for_month,
    get_movements_for_display_month,
    import_santander_portugal_consolidated_statement,
    mark_movement_as_paid,
)


def parse_month_parameter(request):
    """
    Parse month query parameter in YYYY-MM format.

    If the parameter is invalid, return the current month.
    """
    raw_month = request.GET.get("month")

    today = date.today()

    if not raw_month:
        return today.year, today.month

    try:
        year, month = raw_month.split("-")
        parsed_date = date(int(year), int(month), 1)

        return parsed_date.year, parsed_date.month

    except (ValueError, TypeError):
        return today.year, today.month


@login_required
def finance_dashboard_view(request):
    """
    Show financial accounts, monthly balances and movements.
    """
    company = get_user_company(request.user)

    if not company:
        messages.error(request, "Você não está vinculado a nenhuma empresa.")
        return redirect("dashboard")

    year, month = parse_month_parameter(request)

    ensure_fixed_movements_for_month(
        company=company,
        year=year,
        month=month,
    )

    selected_month = date(year, month, 1)
    previous_month = selected_month - relativedelta(months=1)
    next_month = selected_month + relativedelta(months=1)
    current_month = date.today().replace(day=1)

    accounts = FinancialAccount.objects.filter(
        company=company,
        is_active=True,
    ).select_related(
        "bank",
        "holder",
    )

    account_summaries = []

    for account in accounts:
        summary = calculate_account_month_summary(
            account=account,
            year=year,
            month=month,
        )

        account_summaries.append(
            {
                "account": account,
                "summary": summary,
            }
        )

    movements = get_movements_for_display_month(
        company=company,
        year=year,
        month=month,
    )

    can_manage_finance = user_is_company_owner(
        user=request.user,
        company=company,
    )

    return render(
        request,
        "finances/finance_dashboard.html",
        {
            "company": company,
            "year": year,
            "month": month,
            "accounts": accounts,
            "account_summaries": account_summaries,
            "movements": movements,
            "can_manage_finance": can_manage_finance,
            "can_transfer": accounts.count() > 1,
            "selected_month": selected_month,
            "previous_month": previous_month,
            "next_month": next_month,
            "current_month": current_month,
        },
    )


@login_required
def bank_create_view(request):
    """
    Create a bank for the current company.
    """
    company = get_user_company(request.user)

    if not user_is_company_owner(request.user, company):
        messages.error(request, "Você não tem permissão para cadastrar bancos.")
        return redirect("finance_dashboard")

    if request.method == "POST":
        form = BankForm(request.POST)

        if form.is_valid():
            bank = form.save(commit=False)
            bank.company = company
            bank.save()

            messages.success(request, "Banco cadastrado com sucesso.")
            return redirect("finance_dashboard")
    else:
        form = BankForm()

    return render(
        request,
        "finances/bank_form.html",
        {
            "form": form,
        },
    )


@login_required
def financial_account_create_view(request):
    """
    Create a financial account for the current company.
    """
    company = get_user_company(request.user)

    if not user_is_company_owner(request.user, company):
        messages.error(request, "Você não tem permissão para criar contas.")
        return redirect("finance_dashboard")

    if request.method == "POST":
        form = FinancialAccountForm(
            request.POST,
            company=company,
        )

        if form.is_valid():
            account = form.save(commit=False)
            account.company = company
            account.save()

            messages.success(request, "Conta financeira criada com sucesso.")
            return redirect("finance_dashboard")
    else:
        form = FinancialAccountForm(
            company=company,
        )

    return render(
        request,
        "finances/financial_account_form.html",
        {
            "form": form,
        },
    )


@login_required
def financial_movement_create_view(request):
    """
    Create financial movements.
    """
    company = get_user_company(request.user)

    if not user_is_company_owner(request.user, company):
        messages.error(request, "Você não tem permissão para criar movimentos.")
        return redirect("finance_dashboard")

    if request.method == "POST":
        form = FinancialMovementForm(
            request.POST,
            company=company,
        )

        if form.is_valid():
            recurrence_type = form.cleaned_data["recurrence_type"]

            if recurrence_type == FinancialMovement.RecurrenceType.SINGLE:
                create_single_movement(
                    company=company,
                    account=form.cleaned_data["account"],
                    movement_type=form.cleaned_data["movement_type"],
                    amount=form.cleaned_data["amount"],
                    category=form.cleaned_data.get("category"),
                    subcategory=form.cleaned_data.get("subcategory"),
                    due_date=form.cleaned_data["due_date"],
                    description=form.cleaned_data["description"],
                )

            elif recurrence_type == FinancialMovement.RecurrenceType.INSTALLMENT:
                create_installment_movements(
                    company=company,
                    account=form.cleaned_data["account"],
                    movement_type=form.cleaned_data["movement_type"],
                    amount=form.cleaned_data["amount"],
                    due_date=form.cleaned_data["due_date"],
                    installments=form.cleaned_data["installments"],
                    amount_mode=form.cleaned_data["amount_mode"],
                    description=form.cleaned_data["description"],
                )

            elif recurrence_type == FinancialMovement.RecurrenceType.FIXED:
                FinancialMovement.objects.create(
                    company=company,
                    account=form.cleaned_data["account"],
                    movement_type=form.cleaned_data["movement_type"],
                    recurrence_type=FinancialMovement.RecurrenceType.FIXED,
                    description=form.cleaned_data["description"],
                    amount=form.cleaned_data["amount"],
                    due_date=form.cleaned_data["due_date"],
                    status=FinancialMovement.MovementStatus.PENDING,
                    fixed_group=str(uuid.uuid4()),
                    is_fixed_template=True,
                )

            messages.success(request, "Movimento financeiro criado com sucesso.")
            return redirect("finance_dashboard")
    else:
        form = FinancialMovementForm(
            company=company,
        )

    return render(
        request,
        "finances/financial_movement_form.html",
        {
            "form": form,
        },
    )


@login_required
def financial_transfer_create_view(request):
    """
    Create a transfer between financial accounts.
    """
    company = get_user_company(request.user)

    if not user_is_company_owner(request.user, company):
        messages.error(request, "Você não tem permissão para criar transferências.")
        return redirect("finance_dashboard")

    active_accounts_count = FinancialAccount.objects.filter(
        company=company,
        is_active=True,
    ).count()

    if active_accounts_count <= 1:
        messages.error(
            request,
            "É necessário ter pelo menos duas contas ativas para criar uma transferência.",
        )
        return redirect("finance_dashboard")

    if request.method == "POST":
        form = FinancialTransferForm(
            request.POST,
            company=company,
        )

        if form.is_valid():
            create_transfer(
                company=company,
                origin_account=form.cleaned_data["origin_account"],
                destination_account=form.cleaned_data["destination_account"],
                amount=form.cleaned_data["amount"],
                due_date=form.cleaned_data["due_date"],
                description=form.cleaned_data["description"],
            )

            messages.success(request, "Transferência criada com sucesso.")
            return redirect("finance_dashboard")
    else:
        form = FinancialTransferForm(
            company=company,
        )

    return render(
        request,
        "finances/financial_transfer_form.html",
        {
            "form": form,
        },
    )


@login_required
def mark_movement_as_paid_view(request, movement_id):
    """
    Mark a movement as paid with payment date and optional comment.
    """
    company = get_user_company(request.user)

    if not user_is_company_owner(request.user, company):
        messages.error(request, "Você não tem permissão para efetuar movimentos.")
        return redirect("finance_dashboard")

    movement = get_object_or_404(
        FinancialMovement,
        id=movement_id,
        company=company,
        status__in=[
            FinancialMovement.MovementStatus.PENDING,
            FinancialMovement.MovementStatus.OVERDUE,
        ],
    )

    if request.method == "POST":
        form = MarkMovementAsPaidForm(request.POST)

        if form.is_valid():
            mark_movement_as_paid(
                movement=movement,
                payment_comment=form.cleaned_data["payment_comment"],
            )

            messages.success(request, "Movimento marcado como efetuado com sucesso.")

            return redirect("finance_dashboard")
    else:
        form = MarkMovementAsPaidForm()

    return render(
        request,
        "finances/mark_movement_as_paid.html",
        {
            "form": form,
            "movement": movement,
        },
    )


@login_required
def financial_account_detail_view(request, account_id):
    """
    Show internal detail page for a financial account.
    """
    company = get_user_company(request.user)

    if not company:
        messages.error(request, "Você não está vinculado a nenhuma empresa.")
        return redirect("dashboard")

    account = get_object_or_404(
        FinancialAccount.objects.select_related(
            "bank",
            "holder",
        ),
        id=account_id,
        company=company,
    )

    year, month = parse_month_parameter(request)

    ensure_fixed_movements_for_month(
        company=company,
        year=year,
        month=month,
    )

    selected_month = date(year, month, 1)
    previous_month = selected_month - relativedelta(months=1)
    next_month = selected_month + relativedelta(months=1)
    current_month = date.today().replace(day=1)

    summary = calculate_account_month_summary(
        account=account,
        year=year,
        month=month,
    )

    movements = get_movements_for_display_month(
        company=company,
        account=account,
        year=year,
        month=month,
    )

    can_manage_finance = user_is_company_owner(
        user=request.user,
        company=company,
    )

    return render(
        request,
        "finances/financial_account_detail.html",
        {
            "company": company,
            "account": account,
            "summary": summary,
            "movements": movements,
            "selected_month": selected_month,
            "previous_month": previous_month,
            "next_month": next_month,
            "current_month": current_month,
            "can_manage_finance": can_manage_finance,
        },
    )


@login_required
def financial_account_movement_create_view(request, account_id):
    """
    Create a financial movement from an account page.

    The account is filled internally and does not appear in the form.
    """
    company = get_user_company(request.user)

    if not company:
        messages.error(request, "Você não está vinculado a nenhuma empresa.")
        return redirect("dashboard")

    if not user_is_company_owner(request.user, company):
        messages.error(request, "Você não tem permissão para criar movimentos.")
        return redirect("financial_account_detail", account_id=account_id)

    account = get_object_or_404(
        FinancialAccount,
        id=account_id,
        company=company,
        is_active=True,
    )

    if request.method == "POST":
        form = FinancialMovementForm(
            request.POST,
            company=company,
        )

        form.fields["account"].required = False

        if form.is_valid():
            recurrence_type = form.cleaned_data["recurrence_type"]

            if recurrence_type == FinancialMovement.RecurrenceType.SINGLE:
                create_single_movement(
                    company=company,
                    account=account,
                    movement_type=form.cleaned_data["movement_type"],
                    amount=form.cleaned_data["amount"],
                    category=form.cleaned_data.get("category"),
                    subcategory=form.cleaned_data.get("subcategory"),
                    due_date=form.cleaned_data["due_date"],
                    description=form.cleaned_data["description"],
                )

            elif recurrence_type == FinancialMovement.RecurrenceType.INSTALLMENT:
                create_installment_movements(
                    company=company,
                    account=account,
                    movement_type=form.cleaned_data["movement_type"],
                    amount=form.cleaned_data["amount"],
                    due_date=form.cleaned_data["due_date"],
                    installments=form.cleaned_data["installments"],
                    amount_mode=form.cleaned_data["amount_mode"],
                    description=form.cleaned_data["description"],
                )

            elif recurrence_type == FinancialMovement.RecurrenceType.FIXED:
                create_fixed_movements(
                    company=company,
                    account=form.cleaned_data["account"],
                    movement_type=form.cleaned_data["movement_type"],
                    amount=form.cleaned_data["amount"],
                    due_date=form.cleaned_data["due_date"],
                    description=form.cleaned_data["description"],
                )

            messages.success(request, "Movimento financeiro criado com sucesso.")
            return redirect("financial_account_detail", account_id=account.id)
    else:
        form = FinancialMovementForm(
            company=company,
        )

        form.fields["account"].required = False

    del form.fields["account"]

    return render(
        request,
        "finances/financial_account_movement_form.html",
        {
            "form": form,
            "account": account,
        },
    )


@login_required
def bank_statement_import_view(request):
    """
    Import and automatically match Santander bank statement movements.
    """
    company = get_user_company(request.user)

    if not user_is_company_owner(request.user, company):
        messages.error(request, "Você não tem permissão para importar extratos.")
        return redirect("finance_dashboard")

    if request.method == "POST":
        form = BankStatementImportForm(
            request.POST,
            request.FILES,
            company=company,
        )

        if form.is_valid():
            result = import_santander_portugal_consolidated_statement(
                company=company,
                account=form.cleaned_data["account"],
                file_content=form.cleaned_data["file"].read(),
            )

            messages.success(
                request,
                (
                    f"Importação concluída.\n"
                    f"Total de linhas no arquivo: {result['total_lines']}\n"
                    f"Linhas válidas: {result['valid_transactions']}\n"
                    f"Linhas inválidas: {result['invalid_lines']}\n"
                    f"Importados: {result['imported_count']}\n"
                    f"Conciliados: {result['matched_count']}\n"
                    f"Ignorados (duplicados): {result['skipped_count']}"
                ),
            )

            return redirect("finance_dashboard")
    else:
        form = BankStatementImportForm(
            company=company,
        )

    return render(
        request,
        "finances/bank_statement_import.html",
        {
            "form": form,
        },
    )


@login_required
def bank_import_audit_view(request):
    """
    Show audit of imported bank statements.
    """
    company = get_user_company(request.user)

    if not company:
        return redirect("dashboard")

    imports = BankStatementImport.objects.filter(
        company=company,
    ).select_related(
        "account",
        "movement",
    )

    return render(
        request,
        "finances/bank_import_audit.html",
        {
            "imports": imports,
        },
    )


@login_required
def financial_category_create_view(request):
    """
    Create a financial category.
    """
    company = get_user_company(request.user)

    if not user_is_company_owner(request.user, company):
        messages.error(request, "Você não tem permissão para criar categorias.")
        return redirect("finance_dashboard")

    if request.method == "POST":
        form = FinancialCategoryForm(request.POST)

        if form.is_valid():
            category = form.save(commit=False)
            category.company = company
            category.save()

            messages.success(request, "Categoria criada com sucesso.")
            return redirect("finance_dashboard")
    else:
        form = FinancialCategoryForm()

    return render(
        request,
        "finances/financial_category_form.html",
        {
            "form": form,
        },
    )


@login_required
def financial_subcategory_create_view(request):
    """
    Create a financial subcategory.
    """
    company = get_user_company(request.user)

    if not user_is_company_owner(request.user, company):
        messages.error(request, "Você não tem permissão para criar subcategorias.")
        return redirect("finance_dashboard")

    if request.method == "POST":
        form = FinancialSubcategoryForm(
            request.POST,
            company=company,
        )

        if form.is_valid():
            subcategory = form.save(commit=False)
            subcategory.company = company
            subcategory.save()

            messages.success(request, "Subcategoria criada com sucesso.")
            return redirect("finance_dashboard")
    else:
        form = FinancialSubcategoryForm(
            company=company,
        )

    return render(
        request,
        "finances/financial_subcategory_form.html",
        {
            "form": form,
        },
    )
