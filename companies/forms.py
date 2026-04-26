from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from companies.models import Company, CompanyMembership, HierarchyLevel, Role

User = get_user_model()


class CompanyRegistrationForm(forms.Form):
    """
    Form used to create a company and the first owner responsible.
    """

    company_name = forms.CharField(
        label="Nome da empresa",
        max_length=255,
    )

    company_nif = forms.CharField(
        label="NIF da empresa",
        max_length=20,
    )

    company_email = forms.EmailField(
        label="Email da empresa",
        required=False,
    )

    company_phone = forms.CharField(
        label="Telefone da empresa",
        max_length=30,
        required=False,
    )

    company_address = forms.CharField(
        label="Morada da empresa",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
            }
        ),
    )

    owner_full_name = forms.CharField(
        label="Nome completo do dono responsável",
        max_length=255,
    )

    owner_nif = forms.CharField(
        label="NIF do dono responsável",
        max_length=20,
    )

    owner_email = forms.EmailField(
        label="Email do dono responsável",
        required=False,
    )

    password1 = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput,
    )

    password2 = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput,
    )

    def clean_company_nif(self):
        """
        Validate company NIF uniqueness.
        """
        company_nif = self.cleaned_data["company_nif"]

        if User.objects.filter(nif=company_nif).exists():
            raise forms.ValidationError("Já existe um usuário com este NIF.")

        if Company.objects.filter(nif=company_nif).exists():
            raise forms.ValidationError("Já existe uma empresa com este NIF.")

        return company_nif

    def clean_owner_nif(self):
        """
        Validate owner NIF uniqueness.
        """
        owner_nif = self.cleaned_data["owner_nif"]

        if User.objects.filter(nif=owner_nif).exists():
            raise forms.ValidationError("Já existe um usuário com este NIF.")

        return owner_nif

    def clean(self):
        """
        Validate password confirmation and NIF conflicts.
        """
        cleaned_data = super().clean()

        company_nif = cleaned_data.get("company_nif")
        owner_nif = cleaned_data.get("owner_nif")
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if company_nif and owner_nif and company_nif == owner_nif:
            raise forms.ValidationError(
                "O NIF da empresa não pode ser igual ao NIF do dono responsável."
            )

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("As senhas não conferem.")

        return cleaned_data

    @transaction.atomic
    def save(self):
        """
        Create company user, owner user, company profile and owner membership.
        """
        company_user = User.objects.create_user(
            nif=self.cleaned_data["company_nif"],
            email=self.cleaned_data.get("company_email"),
            password=self.cleaned_data["password1"],
            full_name=self.cleaned_data["company_name"],
            user_type=User.UserType.COMPANY,
        )

        owner_user = User.objects.create_user(
            nif=self.cleaned_data["owner_nif"],
            email=self.cleaned_data.get("owner_email"),
            password=self.cleaned_data["password1"],
            full_name=self.cleaned_data["owner_full_name"],
            user_type=User.UserType.PERSON,
        )

        company = Company.objects.create(
            user=company_user,
            name=self.cleaned_data["company_name"],
            nif=self.cleaned_data["company_nif"],
            email=self.cleaned_data.get("company_email", ""),
            phone=self.cleaned_data.get("company_phone", ""),
            address=self.cleaned_data.get("company_address", ""),
        )

        CompanyMembership.objects.create(
            company=company,
            person=owner_user,
            membership_type=CompanyMembership.MembershipType.OWNER,
        )

        return company, owner_user


class PersonMembershipForm(forms.Form):
    """
    Form used to add a person and link them to the authenticated user's company.
    """

    full_name = forms.CharField(
        label="Nome completo",
        max_length=255,
    )

    nif = forms.CharField(
        label="NIF",
        max_length=20,
    )

    email = forms.EmailField(
        label="Email",
        required=False,
    )

    membership_type = forms.ChoiceField(
        label="Tipo de vínculo",
        choices=CompanyMembership.MembershipType.choices,
    )

    role = forms.ModelChoiceField(
        label="Cargo",
        queryset=Role.objects.none(),
        required=False,
    )

    password1 = forms.CharField(
        label="Senha inicial",
        widget=forms.PasswordInput,
    )

    password2 = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput,
    )

    def __init__(self, *args, company=None, **kwargs):
        """
        Receive company to filter available roles.
        """
        super().__init__(*args, **kwargs)

        self.company = company

        if company:
            self.fields["role"].queryset = Role.objects.filter(
                company=company,
                is_active=True,
            )

    def clean_nif(self):
        """
        Validate person NIF uniqueness.
        """
        nif = self.cleaned_data["nif"]

        if User.objects.filter(nif=nif).exists():
            raise forms.ValidationError("Já existe um usuário com este NIF.")

        return nif

    def clean(self):
        """
        Validate password confirmation and employee role requirement.
        """
        cleaned_data = super().clean()

        membership_type = cleaned_data.get("membership_type")
        role = cleaned_data.get("role")
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if membership_type == CompanyMembership.MembershipType.EMPLOYEE and not role:
            raise forms.ValidationError(
                "Ao adicionar funcionário, é obrigatório selecionar um cargo."
            )

        if membership_type != CompanyMembership.MembershipType.EMPLOYEE:
            cleaned_data["role"] = None

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("As senhas não conferem.")

        return cleaned_data

    @transaction.atomic
    def save(self):
        """
        Create person user and company membership.
        """
        person = User.objects.create_user(
            nif=self.cleaned_data["nif"],
            email=self.cleaned_data.get("email"),
            password=self.cleaned_data["password1"],
            full_name=self.cleaned_data["full_name"],
            user_type=User.UserType.PERSON,
        )

        membership = CompanyMembership.objects.create(
            company=self.company,
            person=person,
            membership_type=self.cleaned_data["membership_type"],
            role=self.cleaned_data.get("role"),
        )

        return membership


class HierarchyLevelForm(forms.ModelForm):
    """
    Form used to create hierarchy levels.
    """

    class Meta:
        model = HierarchyLevel
        fields = [
            "name",
            "level",
        ]


class RoleForm(forms.ModelForm):
    """
    Form used to create company roles.
    """

    class Meta:
        model = Role
        fields = [
            "name",
            "hierarchy_level",
        ]

    def __init__(self, *args, company=None, **kwargs):
        """
        Filter hierarchy levels by company.
        """
        super().__init__(*args, **kwargs)

        self.company = company

        if company:
            self.fields["hierarchy_level"].queryset = HierarchyLevel.objects.filter(
                company=company,
            )
