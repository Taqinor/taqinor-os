"""XGED18 — Documents-liens (URL externes comme entrées GED).

Couvre :
  * créer un document-lien le fait apparaître dans l'arbre avec tags/ACL ;
  * les actions fichier (version/OCR/signature) le refusent proprement (400) ;
  * `est_document_lien` dérivé correctement.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, DocumentTag, Folder

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


class XGed18Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged18-a', 'Xged18 A')
        self.admin_a = make_user(self.co_a, 'xged18-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')


class CreerDocumentLienTests(XGed18Base):
    def test_creer_document_lien(self):
        doc = services.creer_document_lien(
            company=self.co_a, folder=self.folder_a, nom='Google Doc Devis',
            url_externe='https://docs.google.com/document/d/xyz',
            created_by=self.admin_a)
        self.assertTrue(doc.est_document_lien)
        self.assertEqual(doc.url_externe, 'https://docs.google.com/document/d/xyz')

    def test_requires_url(self):
        with self.assertRaises(ValueError):
            services.creer_document_lien(
                company=self.co_a, folder=self.folder_a, nom='Sans URL',
                url_externe='')

    def test_appears_in_folder_listing_with_tags(self):
        doc = services.creer_document_lien(
            company=self.co_a, folder=self.folder_a, nom='Lien',
            url_externe='https://example.com/doc')
        tag = DocumentTag.objects.create(
            company=self.co_a, nom='Externe', slug='externe')
        services.assign_tag(doc, tag)
        api = auth(self.admin_a)
        resp = api.get(f'/api/django/ged/documents/?folder={self.folder_a.pk}')
        self.assertEqual(resp.status_code, 200)
        ids = [d['id'] for d in resp.data.get('results', resp.data)]
        self.assertIn(doc.pk, ids)


class GuardTests(XGed18Base):
    def test_assert_not_document_lien_raises_for_link(self):
        doc = services.creer_document_lien(
            company=self.co_a, folder=self.folder_a, nom='Lien',
            url_externe='https://example.com')
        with self.assertRaises(ValueError):
            services.assert_not_document_lien(doc, action='version')

    def test_assert_not_document_lien_passes_for_file_document(self):
        doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Fichier normal')
        services.assert_not_document_lien(doc, action='version')  # no raise

    def test_ajout_version_refuse_400(self):
        doc = services.creer_document_lien(
            company=self.co_a, folder=self.folder_a, nom='Lien',
            url_externe='https://example.com')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/versions/', {
            'document': doc.pk, 'file_key': 'k', 'filename': 'x.pdf',
        })
        self.assertEqual(resp.status_code, 400)

    def test_demander_signature_refuse_400(self):
        doc = services.creer_document_lien(
            company=self.co_a, folder=self.folder_a, nom='Lien',
            url_externe='https://example.com')
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/demandes-signature/', {
            'document': doc.pk, 'signataire_nom': 'Karim',
            'signataire_email': 'k@x.com',
        })
        self.assertEqual(resp.status_code, 400)
