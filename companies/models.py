from django.conf import settings
from django.db import models


class Company(models.Model):
    """
    Company registered in the system.

    The company is represented by a User with user_type COMPANY.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_profile",
        verbose_name="Usuário da empresa",
    )

    name = models.CharField(
        max_length=255,
        verbose_name="Nome da empresa",
    )

    nif = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="NIF da empresa",
    )

    email = models.EmailField(
        blank=True,
        verbose_name="Email",
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Telefone",
    )

    address = models.TextField(
        blank=True,
        verbose_name="Morada",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em",
    )

    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = [
            "name",
        ]

    def __str__(self):
        return self.name


class HierarchyLevel(models.Model):
    """
    Hierarchy level used by company roles.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="hierarchy_levels",
        verbose_name="Empresa",
    )

    name = models.CharField(
        max_length=100,
        verbose_name="Nome",
    )

    level = models.PositiveIntegerField(
        verbose_name="Nível",
        help_text="Lower numbers represent higher hierarchy.",
    )

    class Meta:
        verbose_name = "Nível de hierarquia"
        verbose_name_plural = "Níveis de hierarquia"
        ordering = [
            "level",
            "name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "level",
                ],
                name="unique_hierarchy_level_per_company",
            ),
            models.UniqueConstraint(
                fields=[
                    "company",
                    "name",
                ],
                name="unique_hierarchy_name_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.name} - nível {self.level}"


class Role(models.Model):
    """
    Role used when linking employees to a company.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="roles",
        verbose_name="Empresa",
    )

    name = models.CharField(
        max_length=100,
        verbose_name="Cargo",
    )

    hierarchy_level = models.ForeignKey(
        HierarchyLevel,
        on_delete=models.PROTECT,
        related_name="roles",
        verbose_name="Nível de hierarquia",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo",
    )

    class Meta:
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"
        ordering = [
            "hierarchy_level__level",
            "name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "name",
                ],
                name="unique_role_name_per_company",
            ),
        ]

    def __str__(self):
        return self.name


class CompanyMembership(models.Model):
    """
    Link between a physical person and a company.
    """

    class MembershipType(models.TextChoices):
        OWNER = "OWNER", "Dono responsável"
        EMPLOYEE = "EMPLOYEE", "Funcionário"
        PARTNER = "PARTNER", "Sócio"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Empresa",
    )

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_memberships",
        verbose_name="Pessoa",
    )

    membership_type = models.CharField(
        max_length=20,
        choices=MembershipType.choices,
        verbose_name="Tipo de vínculo",
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="memberships",
        verbose_name="Cargo",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em",
    )

    class Meta:
        verbose_name = "Vínculo com empresa"
        verbose_name_plural = "Vínculos com empresas"
        ordering = [
            "company",
            "person__full_name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "person",
                ],
                name="unique_person_membership_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.person.full_name} - {self.company.name}"

    @property
    def is_owner(self):
        """Return True when the membership is owner responsible."""
        return self.membership_type == self.MembershipType.OWNER

    @property
    def is_employee(self):
        """Return True when the membership is employee."""
        return self.membership_type == self.MembershipType.EMPLOYEE

    @property
    def is_partner(self):
        """Return True when the membership is partner."""
        return self.membership_type == self.MembershipType.PARTNER