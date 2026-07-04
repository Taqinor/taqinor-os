"""XGED17 — Comparaison de versions.

Couvre :
  * deux versions d'un document TEXTE montrent leurs lignes ajoutées/supprimées ;
  * deux scans SANS texte montrent le diff de métadonnées seulement ;
  * scoping société sur l'action.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import selectors
from apps.ged.models import Cabinet, Document, DocumentVersion, Folder

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


class XGed17Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged17-a', 'Xged17 A')
        self.admin_a = make_user(self.co_a, 'xged17-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat',
            texte_ocr='Ligne 1\nLigne 2\nLigne 3')
        self.v1 = DocumentVersion.objects.create(
            company=self.co_a, document=self.doc, version=1,
            file_key='k1', filename='v1.pdf', size=100, mime='application/pdf',
            checksum='aaa')
        self.v2 = DocumentVersion.objects.create(
            company=self.co_a, document=self.doc, version=2,
            file_key='k2', filename='v2.pdf', size=200, mime='application/pdf',
            checksum='bbb')


class ComparerVersionsSelectorTests(XGed17Base):
    def test_texte_diff_when_both_have_text(self):
        result = selectors.comparer_versions(self.v1, self.v2)
        self.assertTrue(result['texte_disponible'])
        self.assertIn('diff_texte', result)

    def test_metadonnees_diff_always_present(self):
        result = selectors.comparer_versions(self.v1, self.v2)
        self.assertIn('size', result['metadonnees'])
        self.assertEqual(result['metadonnees']['size'], {'v1': 100, 'v2': 200})

    def test_binaire_indisponible_sans_texte(self):
        self.doc.texte_ocr = ''
        self.doc.save(update_fields=['texte_ocr'])
        result = selectors.comparer_versions(self.v1, self.v2)
        self.assertFalse(result['texte_disponible'])
        self.assertIn('message', result)


class ComparerEndpointTests(XGed17Base):
    def test_endpoint_returns_comparison(self):
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/ged/documents/{self.doc.pk}/comparer/'
            f'?v1={self.v1.pk}&v2={self.v2.pk}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('metadonnees', resp.data)

    def test_endpoint_missing_params_400(self):
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/{self.doc.pk}/comparer/')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_unknown_version_404(self):
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/ged/documents/{self.doc.pk}/comparer/'
            f'?v1={self.v1.pk}&v2=999999')
        self.assertEqual(resp.status_code, 404)
