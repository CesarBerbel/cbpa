from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """
    Custom manager for User model without username field.
    """

    use_in_migrations = True

    def _create_user(self, nif, email, password, **extra_fields):
        """
        Create and save a user with the given NIF, email and password.
        """
        if not nif:
            raise ValueError("The NIF must be provided.")

        email = self.normalize_email(email)

        user = self.model(
            nif=nif,
            email=email,
            **extra_fields,
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_user(self, nif, email=None, password=None, **extra_fields):
        """
        Create a regular user.
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        return self._create_user(
            nif=nif,
            email=email,
            password=password,
            **extra_fields,
        )

    def create_superuser(self, nif, email=None, password=None, **extra_fields):
        """
        Create a superuser.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("user_type", User.UserType.PERSON)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(
            nif=nif,
            email=email,
            password=password,
            **extra_fields,
        )


class User(AbstractUser):
    """
    Custom user model for CBPA.

    The NIF is used as the authentication username.
    Email is intentionally not unique because the README allows repeated emails.
    """

    class UserType(models.TextChoices):
        COMPANY = "COMPANY", "Empresa"
        PERSON = "PERSON", "Pessoa física"

    username = None

    nif = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="NIF",
        help_text="Unique fiscal identification number used for login.",
    )

    email = models.EmailField(
        blank=True,
        verbose_name="Email",
        help_text="Email can be repeated between users.",
    )

    full_name = models.CharField(
        max_length=255,
        verbose_name="Nome completo",
    )

    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.PERSON,
        verbose_name="Tipo de usuário",
    )

    objects = UserManager()

    USERNAME_FIELD = "nif"

    REQUIRED_FIELDS = [
        "email",
        "full_name",
    ]

    def __str__(self):
        return f"{self.full_name} - {self.nif}"

    @property
    def is_company(self):
        """Return True when the user represents a company."""
        return self.user_type == self.UserType.COMPANY

    @property
    def is_person(self):
        """Return True when the user represents a physical person."""
        return self.user_type == self.UserType.PERSON