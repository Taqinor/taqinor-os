"""Helpers de test partagés du groupe NTJUR.

Chaque suite passe un ``slug`` EXPLICITE et distinct à :func:`make_company` :
deux appels au même slug renverraient la MÊME ligne (``get_or_create``) et un
test « deux sociétés » ne testerait alors plus rien.
"""
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_admin(company, username):
    """Utilisateur au palier Administrateur (``menu_tier == 'admin'``) — le
    seul palier qui voit les dossiers ``confidentiel`` (NTJUR1)."""
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='admin')


def make_responsable(company, username):
    """Utilisateur au palier Responsable — jamais le confidentiel."""
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='responsable')


def make_user(company, username):
    """Utilisateur au palier limité (repli légacy : pas d'écriture)."""
    return User.objects.create_user(
        username=username, password='x', company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api
