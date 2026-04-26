from django.contrib import admin

from companies.models import Company, CompanyMembership, HierarchyLevel, Role


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """
    Admin for companies.
    """

    list_display = [
        "name",
        "nif",
        "email",
        "created_at",
    ]

    search_fields = [
        "name",
        "nif",
        "email",
    ]


@admin.register(HierarchyLevel)
class HierarchyLevelAdmin(admin.ModelAdmin):
    """
    Admin for hierarchy levels.
    """

    list_display = [
        "company",
        "name",
        "level",
    ]

    list_filter = [
        "company",
    ]

    search_fields = [
        "name",
        "company__name",
    ]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin for roles.
    """

    list_display = [
        "company",
        "name",
        "hierarchy_level",
        "is_active",
    ]

    list_filter = [
        "company",
        "is_active",
    ]

    search_fields = [
        "name",
        "company__name",
    ]


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    """
    Admin for company memberships.
    """

    list_display = [
        "company",
        "person",
        "membership_type",
        "role",
        "is_active",
    ]

    list_filter = [
        "company",
        "membership_type",
        "is_active",
    ]

    search_fields = [
        "company__name",
        "person__full_name",
        "person__nif",
    ]