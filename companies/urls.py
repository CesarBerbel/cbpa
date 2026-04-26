from django.urls import path

from companies.views import add_person_view, company_registration_view

urlpatterns = [
    path("cadastro/", company_registration_view, name="company_registration"),
    path("pessoas/adicionar/", add_person_view, name="add_person"),
]