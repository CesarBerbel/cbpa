from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AccountsAuthTestCase(TestCase):
    """
    Tests for custom user authentication.
    """

    def test_create_user_with_nif(self):
        user = User.objects.create_user(
            nif="123456789",
            email="user@example.com",
            password="Testpass123",
            full_name="User Test",
            user_type=User.UserType.PERSON,
        )

        self.assertEqual(user.nif, "123456789")
        self.assertEqual(user.email, "user@example.com")
        self.assertTrue(user.check_password("Testpass123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            nif="987654321",
            email="admin@example.com",
            password="Testpass123",
            full_name="Admin Test",
            user_type=User.UserType.PERSON,
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_authenticate_with_nif(self):
        User.objects.create_user(
            nif="123456789",
            email="user@example.com",
            password="Testpass123",
            full_name="User Test",
            user_type=User.UserType.PERSON,
        )

        user = authenticate(
            username="123456789",
            password="Testpass123",
        )

        self.assertIsNotNone(user)
        self.assertEqual(user.nif, "123456789")

    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)

    def test_login_with_valid_credentials_redirects(self):
        User.objects.create_user(
            nif="123456789",
            email="user@example.com",
            password="Testpass123",
            full_name="User Test",
            user_type=User.UserType.PERSON,
        )

        response = self.client.post(
            reverse("login"),
            data={
                "username": "123456789",
                "password": "Testpass123",
            },
        )

        self.assertEqual(response.status_code, 302)

    def test_login_with_invalid_credentials_shows_form_again(self):
        response = self.client.post(
            reverse("login"),
            data={
                "username": "123456789",
                "password": "WrongPassword",
            },
        )

        self.assertEqual(response.status_code, 200)
