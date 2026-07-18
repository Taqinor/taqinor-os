"""Fixtures partagées des tests NTMAR (fiscal) — pas un fichier de tests."""
from django.contrib.auth import get_user_model

from authentication.models import Company

User = get_user_model()


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)
