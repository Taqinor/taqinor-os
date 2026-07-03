"""XGED16 — Annotations et tampons sur l'image du document (couche séparée).

Couvre :
  * poser une note et un tampon visibles (persistés) ;
  * l'original reste byte-identique (aucune mutation du fichier stocké) ;
  * l'export annoté est un document séparé (nouveau flux, jamais l'original) ;
  * tampons système + tampons société.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    AnnotationDocument, Cabinet, Document, DocumentVersion, Folder,
    TAMPONS_SYSTEME, TamponSociete,
)

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


def _make_pdf_bytes():
    import fitz
    doc = fitz.open()
    doc.new_page()
    out = doc.tobytes()
    doc.close()
    return out


class XGed16Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged16-a', 'Xged16 A')
        self.admin_a = make_user(self.co_a, 'xged16-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat')
        self.original_bytes = _make_pdf_bytes()
        self.version = DocumentVersion.objects.create(
            company=self.co_a, document=self.doc, version=1,
            file_key='attachments/orig.pdf', filename='orig.pdf',
            size=len(self.original_bytes), mime='application/pdf')


class AnnotationCreationTests(XGed16Base):
    def test_creer_note_et_tampon(self):
        note = services.creer_annotation(
            self.version, type_annotation='note', page=0, x=10, y=20,
            contenu='À vérifier', auteur=self.admin_a)
        tampon = services.creer_annotation(
            self.version, type_annotation='tampon', page=0, x=50, y=50,
            contenu='Payé', auteur=self.admin_a)
        self.assertEqual(self.version.annotations.count(), 2)
        self.assertEqual(note.contenu, 'À vérifier')
        self.assertEqual(tampon.type_annotation, 'tampon')

    def test_original_never_mutated(self):
        # Poser une annotation ne touche ni `file_key` ni la taille/checksum de
        # la version — la seule table écrite est `AnnotationDocument`.
        before_key = self.version.file_key
        before_size = self.version.size
        services.creer_annotation(
            self.version, type_annotation='tampon', contenu='Validé')
        self.version.refresh_from_db()
        self.assertEqual(self.version.file_key, before_key)
        self.assertEqual(self.version.size, before_size)


class TamponsTests(XGed16Base):
    def test_tampons_disponibles_inclut_systeme(self):
        tampons = services.tampons_disponibles(self.co_a)
        for t in TAMPONS_SYSTEME:
            self.assertIn(t, tampons)

    def test_tampons_disponibles_inclut_societe(self):
        TamponSociete.objects.create(company=self.co_a, libelle='Archivé RH')
        tampons = services.tampons_disponibles(self.co_a)
        self.assertIn('Archivé RH', tampons)

    def test_tampons_endpoint(self):
        api = auth(self.admin_a)
        resp = api.get('/api/django/ged/annotations/tampons/')
        self.assertEqual(resp.status_code, 200)
        for t in TAMPONS_SYSTEME:
            self.assertIn(t, resp.data)


class ExportAnnoteTests(XGed16Base):
    def test_export_produces_separate_document_original_intact(self):
        services.creer_annotation(
            self.version, type_annotation='tampon', page=0, x=10, y=10,
            contenu='Validé')
        reference_bytes = bytes(self.original_bytes)
        with mock.patch(
                'apps.ged.services._fetch_version_bytes',
                return_value=(self.original_bytes, None)):
            out_bytes = services.exporter_pdf_annote(self.version)
        # Le PDF annoté est un flux DIFFÉRENT (nouveau fichier), et l'appel
        # n'a muté ni l'objet bytes source ni la version en base.
        self.assertNotEqual(out_bytes, reference_bytes)
        self.assertEqual(self.original_bytes, reference_bytes)

    def test_export_without_pymupdf_raises(self):
        with mock.patch.dict('sys.modules', {'fitz': None}):
            with self.assertRaises(ValueError):
                services.exporter_pdf_annote(self.version)


class AnnotationApiTests(XGed16Base):
    def test_create_annotation_via_api(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/annotations/', {
            'version': self.version.pk, 'type_annotation': 'note',
            'page': 0, 'x': 15, 'y': 25, 'contenu': 'Note test',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            AnnotationDocument.objects.filter(
                version=self.version, auteur=self.admin_a).exists())
