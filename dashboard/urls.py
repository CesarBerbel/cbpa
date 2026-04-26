from django.urls import path

from dashboard.views import dashboard_view, home_view

urlpatterns = [
    path("", home_view, name="home"),
    path("dashboard/", dashboard_view, name="dashboard"),
]