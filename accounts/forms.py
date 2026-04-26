from django import forms
from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    """
    Login form using NIF instead of username.
    """

    username = forms.CharField(
        label="NIF",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Digite o NIF",
                "autocomplete": "username",
            }
        ),
    )

    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Digite a senha",
                "autocomplete": "current-password",
            }
        ),
    )