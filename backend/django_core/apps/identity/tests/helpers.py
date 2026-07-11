"""Fabriques partagées des tests de la fondation identité (NTSEC)."""
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


def make_company(slug, nom=None):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom or slug})
    return company


def make_user(company, username, role='admin', **kwargs):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role, **kwargs)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api
