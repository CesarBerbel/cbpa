from django.contrib.auth import get_user_model
from django.test import TestCase

from companies.models import Company, CompanyMembership
from companies.services import user_is_company_owner, get_user_company

User = get_user_model()


class FinancePermissionsTestCase(TestCase):
    """
    Tests for company ownership and finance permissions.
    """

    def setUp(self):
        """
        Create company, owner, employee and partner memberships.
        """
        self.company_user = User.objects.create_user(
            nif="500000001",
            email="empresa@example.com",
            password="Testpass123",
            full_name="Empresa Teste",
            user_type=User.UserType.COMPANY,
        )

        self.owner_user = User.objects.create_user(
            nif="123456789",
            email="owner@example.com",
            password="Testpass123",
            full_name="Dono Responsável",
            user_type=User.UserType.PERSON,
        )

        self.employee_user = User.objects.create_user(
            nif="123456780",
            email="employee@example.com",
            password="Testpass123",
            full_name="Funcionário Teste",
            user_type=User.UserType.PERSON,
        )

        self.partner_user = User.objects.create_user(
            nif="123456781",
            email="partner@example.com",
            password="Testpass123",
            full_name="Sócio Teste",
            user_type=User.UserType.PERSON,
        )

        self.company = Company.objects.create(
            user=self.company_user,
            name="Empresa Teste",
            nif="500000001",
            email="empresa@example.com",
        )

        self.owner_membership = CompanyMembership.objects.create(
            company=self.company,
            person=self.owner_user,
            membership_type=CompanyMembership.MembershipType.OWNER,
        )

        self.employee_membership = CompanyMembership.objects.create(
            company=self.company,
            person=self.employee_user,
            membership_type=CompanyMembership.MembershipType.EMPLOYEE,
        )

        self.partner_membership = CompanyMembership.objects.create(
            company=self.company,
            person=self.partner_user,
            membership_type=CompanyMembership.MembershipType.PARTNER,
        )

    def test_owner_user_can_manage_finance(self):
        """
        Owner responsible should be recognized as company owner.
        """
        self.assertTrue(
            user_is_company_owner(
                user=self.owner_user,
                company=self.company,
            )
        )

    def test_employee_user_cannot_manage_finance(self):
        """
        Employee should not be allowed to manage finance.
        """
        self.assertFalse(
            user_is_company_owner(
                user=self.employee_user,
                company=self.company,
            )
        )

    def test_partner_user_cannot_manage_finance_by_default(self):
        """
        Partner should not be allowed to manage finance by default.
        """
        self.assertFalse(
            user_is_company_owner(
                user=self.partner_user,
                company=self.company,
            )
        )

    def test_company_user_gets_own_company(self):
        """
        Company user should return own company profile.
        """
        company = get_user_company(self.company_user)

        self.assertEqual(company, self.company)

    def test_person_user_gets_membership_company(self):
        """
        Person user should return company from active membership.
        """
        company = get_user_company(self.owner_user)

        self.assertEqual(company, self.company)

    def test_inactive_membership_does_not_allow_ownership(self):
        """
        Inactive owner membership should not allow financial management.
        """
        self.owner_membership.is_active = False
        self.owner_membership.save()

        self.assertFalse(
            user_is_company_owner(
                user=self.owner_user,
                company=self.company,
            )
        )
