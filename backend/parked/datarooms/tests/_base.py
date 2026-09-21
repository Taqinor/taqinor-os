"""Helpers de test partagés du module ``datarooms``.

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
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy='admin')


def make_user(company, username):
    """Utilisateur au palier limité (repli légacy : pas d'écriture)."""
    return User.objects.create_user(
        username=username, password='x', company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_document(company, nom, *, cabinet_nom='Admin', folder_nom='Dossier',
                  file_key=None):
    """Crée un document GED minimal (cabinet + dossier + version courante).

    Les tests de CETTE app ont besoin de vrais documents GED à regrouper ;
    l'import de ``ged.models`` est cantonné aux FIXTURES de test (le code de
    production, lui, ne lit la GED que par ``ged.selectors``)."""
    from apps.ged.models import Cabinet, Document, DocumentVersion, Folder

    cabinet, _ = Cabinet.objects.get_or_create(
        company=company, nom=cabinet_nom)
    folder, _ = Folder.objects.get_or_create(
        company=company, cabinet=cabinet, nom=folder_nom)
    document = Document.objects.create(company=company, folder=folder, nom=nom)
    DocumentVersion.objects.create(
        company=company, document=document, version=1,
        file_key=file_key or f'ged/{company.pk}/{document.pk}.pdf',
        filename=f'{nom}.pdf', mime='application/pdf')
    return document
