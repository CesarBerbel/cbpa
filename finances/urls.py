from django.urls import path

from finances.views import (
    bank_create_view,
    bank_import_audit_view,
    finance_dashboard_view,
    financial_account_create_view,
    financial_account_detail_view,
    financial_account_movement_create_view,
    financial_movement_create_view,
    financial_transfer_create_view,
    mark_movement_as_paid_view,
    bank_statement_import_view,
    financial_category_create_view,
    financial_subcategory_create_view,
)

urlpatterns = [
    path("financeiro/", finance_dashboard_view, name="finance_dashboard"),
    path("financeiro/bancos/novo/", bank_create_view, name="bank_create"),
    path(
        "financeiro/contas/nova/",
        financial_account_create_view,
        name="financial_account_create",
    ),
    path(
        "financeiro/contas/<int:account_id>/",
        financial_account_detail_view,
        name="financial_account_detail",
    ),
    path(
        "financeiro/contas/<int:account_id>/movimentos/novo/",
        financial_account_movement_create_view,
        name="financial_account_movement_create",
    ),
    path(
        "financeiro/movimentos/novo/",
        financial_movement_create_view,
        name="financial_movement_create",
    ),
    path(
        "financeiro/movimentos/<int:movement_id>/efetuar/",
        mark_movement_as_paid_view,
        name="mark_movement_as_paid",
    ),
    path(
        "financeiro/transferencias/nova/",
        financial_transfer_create_view,
        name="financial_transfer_create",
    ),
    path(
        "financeiro/extratos/importar/",
        bank_statement_import_view,
        name="bank_statement_import",
    ),
    path(
        "financeiro/extratos/auditoria/",
        bank_import_audit_view,
        name="bank_import_audit",
    ),
    path(
        "financeiro/categorias/nova/",
        financial_category_create_view,
        name="financial_category_create",
    ),
    path(
        "financeiro/subcategorias/nova/",
        financial_subcategory_create_view,
        name="financial_subcategory_create",
    ),
]
