from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Admin configuration for the custom User model.
    """

    model = User

    list_display = (
        "nif",
        "full_name",
        "email",
        "user_type",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "user_type",
        "is_staff",
        "is_superuser",
        "is_active",
    )

    search_fields = (
        "nif",
        "full_name",
        "email",
    )

    ordering = ("full_name",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nif",
                    "password",
                )
            },
        ),
        (
            "Informações pessoais",
            {
                "fields": (
                    "full_name",
                    "email",
                    "user_type",
                )
            },
        ),
        (
            "Permissões",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Datas importantes",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "nif",
                    "email",
                    "full_name",
                    "user_type",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_superuser",
                    "is_active",
                ),
            },
        ),
    )
