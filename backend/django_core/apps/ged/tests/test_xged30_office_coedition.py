"""XGED30 — Co-édition Office (Collabora/OnlyOffice self-host, gated).

Couvre :
  * sans `GED_OFFICE_URL`, aucune UI ni appel (no-op complet, 400 explicite) ;
  * avec l'URL posée, le cycle ouvrir -> éditer -> sauver crée une NOUVELLE
    version (check-out respecté) ;
  * gardes GED23/24 (archivé/hold -> refus, jamais une 500) ;
  * check-out par un tiers -> 409 à la sauvegarde.
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import Cabinet, Document, Folder, LegalHold

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


class XGed30Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged30-a', 'Xged30 A')
        self.admin_a = make_user(self.co_a, 'xged30-admin-a', 'admin')
        self.autre_a = make_user(self.co_a, 'xged30-autre-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Contrats')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='contrat.docx')


class ServiceTests(XGed30Base):
    def test_sans_url_office_active_false(self):
        with override_settings(GED_OFFICE_URL=''):
            self.assertFalse(services.office_edit_active())

    def test_avec_url_office_active_true(self):
        with override_settings(GED_OFFICE_URL='https://office.example.com'):
            self.assertTrue(services.office_edit_active())
            self.assertEqual(
                services.office_edit_url(), 'https://office.example.com')

    def test_ouvrir_sans_url_leve(self):
        with override_settings(GED_OFFICE_URL=''):
            with self.assertRaises(ValueError):
                services.ouvrir_dans_editeur_office(self.doc, user=self.admin_a)

    def test_cycle_ouvrir_puis_sauvegarder_cree_version(self):
        with override_settings(GED_OFFICE_URL='https://office.example.com'):
            data = services.ouvrir_dans_editeur_office(
                self.doc, user=self.admin_a)
            self.assertEqual(data['editor_url'], 'https://office.example.com')
            self.doc.refresh_from_db()
            self.assertEqual(self.doc.locked_by_id, self.admin_a.pk)

            version = services.sauvegarder_depuis_editeur_office(
                self.doc, contenu_bytes=b'contenu docx edite',
                user=self.admin_a, filename='contrat.docx',
                mime='application/vnd.openxmlformats-officedocument'
                     '.wordprocessingml.document')
            self.assertEqual(version.document_id, self.doc.pk)
            self.assertEqual(self.doc.versions.count(), 1)

    def test_hold_actif_refuse_ouverture(self):
        LegalHold.objects.create(
            company=self.co_a, document=self.doc, place_par=self.admin_a,
            actif=True)
        with override_settings(GED_OFFICE_URL='https://office.example.com'):
            with self.assertRaises(Exception):
                services.ouvrir_dans_editeur_office(
                    self.doc, user=self.admin_a)

    def test_sauvegarde_par_tiers_verrouille_leve_permission_error(self):
        with override_settings(GED_OFFICE_URL='https://office.example.com'):
            services.ouvrir_dans_editeur_office(self.doc, user=self.admin_a)
            with self.assertRaises(PermissionError):
                services.sauvegarder_depuis_editeur_office(
                    self.doc, contenu_bytes=b'x', user=self.autre_a,
                    filename='contrat.docx')


class ViewTests(XGed30Base):
    def test_endpoint_sans_url_400(self):
        with override_settings(GED_OFFICE_URL=''):
            api = auth(self.admin_a)
            resp = api.post(
                f'/api/django/ged/documents/{self.doc.pk}/office-ouvrir/')
            self.assertEqual(resp.status_code, 400)

    def test_endpoint_cycle_complet(self):
        with override_settings(GED_OFFICE_URL='https://office.example.com'):
            api = auth(self.admin_a)
            resp = api.post(
                f'/api/django/ged/documents/{self.doc.pk}/office-ouvrir/')
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(
                resp.data['editor_url'], 'https://office.example.com')

            mime = (
                'application/vnd.openxmlformats-officedocument'
                '.wordprocessingml.document')
            upload = SimpleUploadedFile(
                'contrat.docx', b'contenu edite', content_type=mime)
            resp2 = api.post(
                f'/api/django/ged/documents/{self.doc.pk}/office-sauvegarder/',
                {'file': upload}, format='multipart')
            self.assertEqual(resp2.status_code, 201, resp2.data)
