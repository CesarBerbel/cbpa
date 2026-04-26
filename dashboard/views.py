from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from companies.services import (
    get_user_company,
    get_user_membership,
    user_is_company_owner,
)


def home_view(request):
    """
    Redirect anonymous users to login and authenticated users to dashboard.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    return redirect("login")


@login_required
def dashboard_view(request):
    """
    Main dashboard for authenticated users.
    """
    company = get_user_company(request.user)
    membership = get_user_membership(
        user=request.user,
        company=company,
    )

    is_owner = user_is_company_owner(
        user=request.user,
        company=company,
    )

    return render(
        request,
        "dashboard/dashboard.html",
        {
            "company": company,
            "membership": membership,
            "is_owner": is_owner,
        },
    )
