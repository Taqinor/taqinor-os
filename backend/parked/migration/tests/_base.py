"""Helpers de test partagés du groupe NTMIG.

Chaque suite passe un ``slug`` EXPLICITE et distinct à :func:`make_company` :
deux appels au même slug renverraient la même ligne (``get_or_create``) et un
test « deux sociétés » ne testerait alors plus rien.
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def make_admin(company, username):
    """Utilisateur au palier Administrateur (``menu_tier == 'admin'``), requis
    par les viewsets NTMIG."""
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='admin')


def make_user(company, username):
    """Utilisateur au palier limité — doit être refusé par les viewsets."""
    return User.objects.create_user(
        username=username, password='x', company=company)


def auth(user):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api
