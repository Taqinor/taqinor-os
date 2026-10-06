"""ADOC16 — une ACL portail (client / rôle partenaire) ne cache rien en interne.

Rejoue la sonde #44 de l'audit documents (2026-10-05) : avant l'ACL client,
le document était listé pour un employé « normal » (GET 200) ; après
AclGed(client=…), il disparaissait de sa liste (GET 404).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ged import selectors
from apps.ged.models import AclGed, Cabinet, Document, Folder
from apps.roles.models import Role
from apps.roles.permissions_registre import ROLE_PORTAIL_PARTENAIRE
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/ged/documents/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data else data
    return [r['id'] for r in rows]


class AclPortailTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc16', defaults={'nom': 'ADOC16'})[0]
        self.normal = User.objects.create_user(
            username='adoc16-normal', password='x', company=self.co,
            role_legacy='normal')
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        folder = Folder.objects.create(company=self.co, cabinet=cab, nom='R')
        self.doc = Document.objects.create(
            company=self.co, folder=folder, nom='Fiche produit')
        self.client_a = Client.objects.create(
            company=self.co, nom='Client A', email='a@example.com')
        self.role_partenaire, _ = Role.objects.get_or_create(
            company=self.co, nom=ROLE_PORTAIL_PARTENAIRE)

    def _voit(self):
        api = auth(self.normal)
        return (self.doc.pk in ids(api.get(BASE)),
                api.get(f'{BASE}{self.doc.pk}/').status_code)

    def test_acl_client_ne_cache_pas_interne(self):
        self.assertEqual(self._voit(), (True, 200))
        AclGed.objects.create(company=self.co, document=self.doc,
                              client=self.client_a, niveau='lecture')
        self.assertEqual(self._voit(), (True, 200))

    def test_acl_role_partenaire_ne_cache_pas_interne(self):
        AclGed.objects.create(company=self.co, document=self.doc,
                              role=self.role_partenaire, niveau='lecture')
        self.assertEqual(self._voit(), (True, 200))
        self.assertFalse(selectors.acl_governs_target(self.doc))

    def test_portail_voit_toujours(self):
        AclGed.objects.create(company=self.co, document=self.doc,
                              client=self.client_a, niveau='lecture')
        AclGed.objects.create(company=self.co, document=self.doc,
                              role=self.role_partenaire, niveau='lecture')
        self.assertIn(self.doc, selectors.documents_partages_client_portail(
            self.co, self.client_a.pk))
        self.assertIn(self.doc, selectors.ressources_partenaire_portail(self.co))
        self.assertEqual(AclGed.objects.filter(document=self.doc).count(), 2)
