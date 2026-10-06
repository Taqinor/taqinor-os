"""ADOC24 — un document déposé par une autre app est trouvable en recherche.

Constat C-ADOC-026 de l'audit documents (2026-10-05) : deposit_document
créait le document sans calculer son `search_vector` → 0 résultat.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ged import services
from apps.ged.models import Document
from authentication.models import Company

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RechercheDepotsTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc24', defaults={'nom': 'ADOC24'})[0]
        self.user = User.objects.create_user(
            username='adoc24-user', password='x', company=self.co,
            role_legacy='normal')

    def test_deposit_document_trouvable(self):
        with mock.patch('apps.ged.services._store_bytes',
                        return_value=('attachments/d.pdf',
                                      {'filename': 'd.pdf', 'size': 6,
                                       'mime': 'application/pdf'})):
            document, cree = services.deposit_document(
                company=self.co, nom='Contrat Dupont', source_type='t',
                source_id=1, contenu_bytes=b'%PDF-1')
        self.assertTrue(cree)
        self.assertIsNotNone(
            Document.objects.get(pk=document.pk).search_vector)
        resp = auth(self.user).get(
            '/api/django/ged/documents/recherche/?q=Dupont')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.data['results'] if isinstance(resp.data, dict) \
            and 'results' in resp.data else resp.data
        self.assertIn(document.pk, [d['id'] for d in data])
