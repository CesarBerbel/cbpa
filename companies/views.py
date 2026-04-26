from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from companies.forms import CompanyRegistrationForm, PersonMembershipForm
from companies.models import CompanyMembership
from companies.services import get_user_company, user_can_manage_company_people


def company_registration_view(request):
    """
    Create a company and the first owner responsible.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = CompanyRegistrationForm(request.POST)

        if form.is_valid():
            company, owner_user = form.save()

            login(request, owner_user)

            messages.success(
                request,
                "Empresa cadastrada com sucesso.",
            )

            return redirect("dashboard")
    else:
        form = CompanyRegistrationForm()

    return render(
        request,
        "companies/company_registration.html",
        {
            "form": form,
        },
    )


@login_required
def add_person_view(request):
    """
    Add a person and link them to the current company.
    """
    company = get_user_company(request.user)

    if not company:
        messages.error(
            request,
            "Você não está vinculado a nenhuma empresa.",
        )
        return redirect("dashboard")

    if not user_can_manage_company_people(request.user, company):
        messages.error(
            request,
            "Você não tem permissão para adicionar pessoas.",
        )
        return redirect("dashboard")

    if request.method == "POST":
        form = PersonMembershipForm(
            request.POST,
            company=company,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Pessoa adicionada com sucesso.",
            )

            return redirect("dashboard")
    else:
        form = PersonMembershipForm(
            company=company,
        )

    memberships = CompanyMembership.objects.select_related(
        "person",
        "role",
    ).filter(
        company=company,
        is_active=True,
    )

    return render(
        request,
        "companies/add_person.html",
        {
            "form": form,
            "company": company,
            "memberships": memberships,
        },
    )
