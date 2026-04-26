from decimal import Decimal

from django import forms
from django.utils import timezone

from companies.models import CompanyMembership
from finances.models import (
    Bank,
    FinancialAccount,
    FinancialCategory,
    FinancialMovement,
    FinancialSubcategory,
)


class BankForm(forms.ModelForm):
    """
    Form used to create company banks.
    """

    class Meta:
        model = Bank
        fields = [
            "name",
        ]


class FinancialAccountForm(forms.ModelForm):
    """
    Form used to create financial accounts.

    The same holder cannot have two accounts for the same bank in the same company.
    """

    class Meta:
        model = FinancialAccount
        fields = [
            "bank",
            "holder",
            "initial_balance",
        ]

    def __init__(self, *args, company=None, **kwargs):
        """
        Filter banks and holders by company.
        """
        super().__init__(*args, **kwargs)

        self.company = company

        if company:
            company_user = company.user

            linked_people = CompanyMembership.objects.filter(
                company=company,
                is_active=True,
            ).values_list(
                "person_id",
                flat=True,
            )

            self.fields["bank"].queryset = Bank.objects.filter(
                company=company,
                is_active=True,
            )

            self.fields["holder"].queryset = self.fields["holder"].queryset.model.objects.filter(
                id__in=[
                    company_user.id,
                    *linked_people,
                ],
            )

    def clean(self):
        """
        Validate duplicated financial account by company, bank and holder.
        """
        cleaned_data = super().clean()

        bank = cleaned_data.get("bank")
        holder = cleaned_data.get("holder")

        if self.company and bank and holder:
            account_exists = FinancialAccount.objects.filter(
                company=self.company,
                bank=bank,
                holder=holder,
            ).exists()

            if account_exists:
                raise forms.ValidationError(
                    "Este titular já possui uma conta financeira para este banco nesta empresa."
                )

        return cleaned_data


class FinancialMovementForm(forms.Form):
    """
    Form used to create single, installment or fixed movements.
    """

    AMOUNT_MODE_CHOICES = [
        ("TOTAL", "O valor informado é o total"),
        ("INSTALLMENT", "O valor informado é o valor de cada parcela"),
    ]

    account = forms.ModelChoiceField(
        label="Conta",
        queryset=FinancialAccount.objects.none(),
    )

    movement_type = forms.ChoiceField(
        label="Tipo",
        choices=FinancialMovement.MovementType.choices,
    )

    category = forms.ModelChoiceField(
        label="Categoria",
        queryset=FinancialCategory.objects.none(),
        required=False,
    )

    subcategory = forms.ModelChoiceField(
        label="Subcategoria",
        queryset=FinancialSubcategory.objects.none(),
        required=False,
    )

    recurrence_type = forms.ChoiceField(
        label="Recorrência",
        choices=FinancialMovement.RecurrenceType.choices,
    )

    description = forms.CharField(
        label="Descrição",
        required=False,
        max_length=255,
    )

    amount = forms.DecimalField(
        label="Valor",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    due_date = forms.DateField(
        label="Data de vencimento",
        initial=timezone.localdate,
        widget=forms.DateInput(
            attrs={
                "type": "date",
            }
        ),
    )

    installments = forms.IntegerField(
        label="Número de parcelas",
        required=False,
        min_value=2,
    )

    amount_mode = forms.ChoiceField(
        label="Como interpretar o valor?",
        choices=AMOUNT_MODE_CHOICES,
        required=False,
    )

    def __init__(self, *args, company=None, **kwargs):
        """
        Filter accounts by company.
        """
        super().__init__(*args, **kwargs)

        self.company = company

        if company:
            self.fields["account"].queryset = FinancialAccount.objects.filter(
                company=company,
                is_active=True,
            )

            self.fields["category"].queryset = FinancialCategory.objects.filter(
                company=company,
                is_active=True,
            )

            self.fields["subcategory"].queryset = FinancialSubcategory.objects.filter(
                company=company,
                is_active=True,
            )

    def clean(self):
        """
        Validate recurrence-specific fields.
        """
        cleaned_data = super().clean()

        recurrence_type = cleaned_data.get("recurrence_type")
        installments = cleaned_data.get("installments")
        amount_mode = cleaned_data.get("amount_mode")
        fixed_months = cleaned_data.get("fixed_months")
        category = cleaned_data.get("category")
        subcategory = cleaned_data.get("subcategory")
        movement_type = cleaned_data.get("movement_type")

        if category and category.movement_type != movement_type:
            raise forms.ValidationError(
                "A categoria selecionada não pertence ao tipo de movimentação escolhido."
            )

        if subcategory and category and subcategory.category != category:
            raise forms.ValidationError(
                "A subcategoria selecionada não pertence à categoria escolhida."
            )

        if recurrence_type == FinancialMovement.RecurrenceType.INSTALLMENT:
            if not installments:
                raise forms.ValidationError("Informe o número de parcelas.")

            if not amount_mode:
                raise forms.ValidationError("Informe se o valor é total ou por parcela.")

        return cleaned_data


class FinancialTransferForm(forms.Form):
    """
    Form used to create transfers between accounts.
    """

    origin_account = forms.ModelChoiceField(
        label="Conta de origem",
        queryset=FinancialAccount.objects.none(),
    )

    destination_account = forms.ModelChoiceField(
        label="Conta de destino",
        queryset=FinancialAccount.objects.none(),
    )

    amount = forms.DecimalField(
        label="Valor",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    due_date = forms.DateField(
        label="Data",
        initial=timezone.localdate,
        widget=forms.DateInput(
            attrs={
                "type": "date",
            }
        ),
    )

    description = forms.CharField(
        label="Descrição",
        required=False,
        max_length=255,
    )

    def __init__(self, *args, company=None, **kwargs):
        """
        Filter accounts by company.
        """
        super().__init__(*args, **kwargs)

        self.company = company

        if company:
            accounts = FinancialAccount.objects.filter(
                company=company,
                is_active=True,
            )

            self.fields["origin_account"].queryset = accounts
            self.fields["destination_account"].queryset = accounts

    def clean(self):
        """
        Validate transfer accounts.
        """
        cleaned_data = super().clean()

        origin_account = cleaned_data.get("origin_account")
        destination_account = cleaned_data.get("destination_account")

        if origin_account and destination_account and origin_account == destination_account:
            raise forms.ValidationError(
                "A conta de origem não pode ser igual à conta de destino."
            )

        return cleaned_data
    
    
class MarkMovementAsPaidForm(forms.Form):
    """
    Form used to mark a movement as paid.
    """

    paid_at = forms.DateField(
        label="Data de efetivação",
        initial=timezone.localdate,
        widget=forms.DateInput(
            attrs={
                "type": "date",
            }
        ),
    )

    payment_comment = forms.CharField(
        label="Comentário",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
            }
        ),
    )    


class BankStatementImportForm(forms.Form):
    """
    Form used to upload bank statement files.
    """

    account = forms.ModelChoiceField(
        label="Conta financeira",
        queryset=FinancialAccount.objects.none(),
    )

    file = forms.FileField(
        label="Arquivo CSV/TXT",
    )

    def __init__(self, *args, company=None, **kwargs):
        """
        Filter accounts by company.
        """
        super().__init__(*args, **kwargs)

        if company:
            self.fields["account"].queryset = FinancialAccount.objects.filter(
                company=company,
                is_active=True,
            )


class FinancialCategoryForm(forms.ModelForm):
    """
    Form used to create financial categories.
    """

    class Meta:
        model = FinancialCategory
        fields = [
            "movement_type",
            "name",
        ]


class FinancialSubcategoryForm(forms.ModelForm):
    """
    Form used to create financial subcategories.
    """

    class Meta:
        model = FinancialSubcategory
        fields = [
            "category",
            "name",
        ]

    def __init__(self, *args, company=None, **kwargs):
        """
        Filter categories by company.
        """
        super().__init__(*args, **kwargs)

        if company:
            self.fields["category"].queryset = FinancialCategory.objects.filter(
                company=company,
                is_active=True,
            )            