"""ZGED7 — Favoris de dossiers/documents + accès rapide.

Couvre :
  * favoriser/défavoriser un dossier togglent ;
  * `mes-favoris/` ne renvoie que les favoris de l'appelant ;
  * un collègue ne voit pas mes favoris ;
  * cible double interdite (clean()).
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged.models import Cabinet, Document, FavoriGed, Folder

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZGed7Base(TestCase):
    def setUp(self):
        self.co_a = make_company('zged7-a', 'Zged7 A')
        self.admin_a = make_user(self.co_a, 'zged7-admin-a', 'admin')
        self.autre_a = make_user(self.co_a, 'zged7-autre-a', 'normal')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='contrat.pdf')


class ModelTests(ZGed7Base):
    def test_cible_double_interdite(self):
        favori = FavoriGed(
            company=self.co_a, utilisateur=self.admin_a,
            folder=self.folder_a, document=self.doc)
        with self.assertRaises(ValidationError):
            favori.clean()

    def test_aucune_cible_interdite(self):
        favori = FavoriGed(company=self.co_a, utilisateur=self.admin_a)
        with self.assertRaises(ValidationError):
            favori.clean()


class ViewTests(ZGed7Base):
    def test_favoriser_defavoriser_dossier_toggle(self):
        api = auth(self.admin_a)
        resp1 = api.post(f'/api/django/ged/dossiers/{self.folder_a.pk}/favori/')
        self.assertEqual(resp1.status_code, 200, resp1.data)
        self.assertTrue(resp1.data['favori'])
        resp2 = api.post(f'/api/django/ged/dossiers/{self.folder_a.pk}/favori/')
        self.assertFalse(resp2.data['favori'])

    def test_favoriser_document_toggle(self):
        api = auth(self.admin_a)
        resp1 = api.post(f'/api/django/ged/documents/{self.doc.pk}/favori/')
        self.assertTrue(resp1.data['favori'])
        resp2 = api.post(f'/api/django/ged/documents/{self.doc.pk}/favori/')
        self.assertFalse(resp2.data['favori'])

    def test_mes_favoris_ne_renvoie_que_les_miens(self):
        api_admin = auth(self.admin_a)
        api_autre = auth(self.autre_a)
        api_admin.post(f'/api/django/ged/dossiers/{self.folder_a.pk}/favori/')
        api_admin.post(f'/api/django/ged/documents/{self.doc.pk}/favori/')

        resp_admin = api_admin.get('/api/django/ged/mes-favoris/')
        self.assertEqual(len(resp_admin.data['dossiers']), 1)
        self.assertEqual(len(resp_admin.data['documents']), 1)

        resp_autre = api_autre.get('/api/django/ged/mes-favoris/')
        self.assertEqual(len(resp_autre.data['dossiers']), 0)
        self.assertEqual(len(resp_autre.data['documents']), 0)

    def test_isolation_societe(self):
        co_b = make_company('zged7-b', 'Zged7 B')
        admin_b = make_user(co_b, 'zged7-admin-b', 'admin')
        api_b = auth(admin_b)
        resp = api_b.post(f'/api/django/ged/dossiers/{self.folder_a.pk}/favori/')
        self.assertEqual(resp.status_code, 404)
