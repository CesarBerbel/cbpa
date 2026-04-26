from companies.models import Company, CompanyMembership


def get_user_company(user):
    """
    Return the company related to the current user.

    Company users return their own company profile.
    Person users return the first active company membership.
    """
    if not user.is_authenticated:
        return None

    if user.is_company and hasattr(user, "company_profile"):
        return user.company_profile

    membership = (
        CompanyMembership.objects.select_related("company")
        .filter(
            person=user,
            is_active=True,
        )
        .first()
    )

    if membership:
        return membership.company

    return None


def get_user_membership(user, company=None):
    """
    Return the active membership for a user in a company.
    """
    if not user.is_authenticated or user.is_company:
        return None

    queryset = CompanyMembership.objects.filter(
        person=user,
        is_active=True,
    )

    if company:
        queryset = queryset.filter(company=company)

    return queryset.first()


def user_is_company_owner(user, company=None):
    """
    Check whether the user is the owner responsible of the company.
    """
    membership = get_user_membership(
        user=user,
        company=company,
    )

    return bool(membership and membership.is_owner)


def user_can_manage_company_people(user, company=None):
    """
    Check whether the user can manage company people.
    """
    return user_is_company_owner(
        user=user,
        company=company,
    )
