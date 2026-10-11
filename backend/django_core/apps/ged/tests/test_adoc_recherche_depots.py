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

    def _ids_recherche(self, q):
        resp = auth(self.user).get(f'/api/django/ged/documents/recherche/?q={q}')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.data['results'] if isinstance(resp.data, dict) \
            and 'results' in resp.data else resp.data
        return [d['id'] for d in data]

    def test_version_versionnee_trouvable(self):
        """ADOC180 — un document créé hors `create_document` (ex.
        `publier_documents_meryem`) puis versionné par `versionner_si_modifie`
        devient trouvable ; une republication réindexe (mot ajouté)."""
        cabinet = services.ensure_cabinet(self.co, 'Documentation')
        dossier = services.ensure_root_folder(
            self.co, cabinet=cabinet, nom='Guides')
        document = Document.objects.create(
            company=self.co, folder=dossier,
            nom='Guide devis pompage solaire')
        self.assertIsNone(Document.objects.get(pk=document.pk).search_vector)
        stockage = {'file_key': 'attachments/g.pdf', 'filename': 'g.pdf',
                    'size': 6, 'mime': 'application/pdf'}
        version, cree = services.versionner_si_modifie(
            document, b'%PDF-1', stocker=lambda: stockage)
        self.assertTrue(cree)
        self.assertIsNotNone(
            Document.objects.get(pk=document.pk).search_vector)
        self.assertIn(document.pk, self._ids_recherche('pompage'))
        Document.objects.filter(pk=document.pk).update(
            description='Forage immergé')
        document.refresh_from_db()
        services.versionner_si_modifie(
            document, b'%PDF-2', stocker=lambda: stockage)
        self.assertIn(document.pk, self._ids_recherche('forage'))
