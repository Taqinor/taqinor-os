"""ADOC21 — un dossier ne se déplace pas par PATCH parent/cabinet.

Constat #23 de l'audit documents (2026-10-05) : PATCH {parent: B} sur A (A
parent de B) → 200 et chemins matérialisés périmés (cycle possible).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged.models import Cabinet, Folder
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/dossiers/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DossierPatchTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc21', defaults={'nom': 'ADOC21'})[0]
        self.resp = User.objects.create_user(
            username='adoc21-resp', password='x', company=self.co,
            role_legacy='responsable')
        self.cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.autre_cab = Cabinet.objects.create(company=self.co, nom='Autre')
        self.a = Folder.objects.create(company=self.co, cabinet=self.cab,
                                       nom='A')
        self.b = Folder.objects.create(company=self.co, cabinet=self.cab,
                                       parent=self.a, nom='B')

    def _etat(self):
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        return (self.a.parent_id, self.a.cabinet_id, self.a.path,
                self.b.parent_id, self.b.cabinet_id, self.b.path)

    def test_patch_parent_ignore(self):
        avant = self._etat()
        api = auth(self.resp)
        for corps in ({'parent': self.b.pk}, {'cabinet': self.autre_cab.pk}):
            resp = api.patch(f'{BASE}{self.a.pk}/', corps, format='json')
            self.assertIn(resp.status_code, (200, 400), resp.content)
            self.assertEqual(self._etat(), avant)
        # Renommer reste possible.
        resp = api.patch(f'{BASE}{self.a.pk}/', {'nom': 'A2'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.a.refresh_from_db()
        self.assertEqual(self.a.nom, 'A2')

    def test_deplacer_vers_descendant_cycle_400(self):
        avant = self._etat()
        resp = auth(self.resp).post(f'{BASE}{self.a.pk}/deplacer/',
                                    {'parent': self.b.pk}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(self._etat(), avant)
        self.assertEqual(self.b.path, f'/{self.a.pk}/{self.b.pk}/')
