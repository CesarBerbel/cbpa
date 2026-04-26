from django.contrib.auth.views import LoginView, LogoutView

from accounts.forms import LoginForm


class UserLoginView(LoginView):
    """
    Login view for users authenticated by NIF.
    """

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class UserLogoutView(LogoutView):
    """
    Logout view.

    Logout should be performed by POST for better security.
    """

    http_method_names = [
        "post",
    ]