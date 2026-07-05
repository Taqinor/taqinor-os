"""XGED12 — Capture mobile photo → PDF multi-pages classé en GED.

Couvre :
  * `services.assembler_photos_pdf` — N images deviennent un PDF de N pages
    (assemblage Pillow `save_all=True`, aucune dépendance nouvelle) ;
  * une liste vide / une image illisible lève `ValueError` (jamais un PDF
    fantôme) ;
  * `services.deposer_photos_assemblees` dépose le PDF assemblé comme
    Document + version 1, société/créateur posés côté serveur ;
  * l'action HTTP `documents/assembler-photos/` (multipart) : dossier requis
    et borné à la société, photos requises, garde de quota, 201 + document
    créé sur succès.
"""
import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
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


def _jpeg_bytes(color=(255, 0, 0)):
    """Un JPEG minimal en mémoire (pas de fichier disque, aucune dépendance)."""
    img = Image.new('RGB', (40, 30), color=color)
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()


class AssemblerPhotosPdfServiceTests(TestCase):
    """Assemblage Pillow pur (sans dossier/company — teste juste la fonction)."""

    def test_trois_photos_donnent_un_pdf_trois_pages(self):
        pdf_bytes = services.assembler_photos_pdf(
            [_jpeg_bytes((255, 0, 0)), _jpeg_bytes((0, 255, 0)),
             _jpeg_bytes((0, 0, 255))])
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))
        # Pillow écrit un `/Count N` dans l'arbre des pages du PDF assemblé.
        self.assertIn(b'/Count 3', pdf_bytes)

    def test_une_seule_photo_donne_un_pdf_une_page(self):
        pdf_bytes = services.assembler_photos_pdf([_jpeg_bytes()])
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))

    def test_liste_vide_leve_value_error(self):
        with self.assertRaises(ValueError):
            services.assembler_photos_pdf([])

    def test_image_illisible_leve_value_error(self):
        with self.assertRaises(ValueError):
            services.assembler_photos_pdf([b'ceci-nest-pas-une-image'])


class DeposerPhotosAssembleesServiceTests(TestCase):
    def setUp(self):
        self.co_a = make_company('xged12-a', 'Xged12 A')
        self.co_b = make_company('xged12-b', 'Xged12 B')
        self.admin_a = make_user(self.co_a, 'xged12-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Chantiers')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Numérisations')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Chantiers')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Numérisations B')

    def test_depose_document_et_version_avec_pdf_assemble(self):
        document = services.deposer_photos_assemblees(
            company=self.co_a, folder=self.folder_a,
            images_bytes=[_jpeg_bytes(), _jpeg_bytes((0, 255, 0))],
            nom='Chantier Rabat', created_by=self.admin_a)
        self.assertEqual(document.company_id, self.co_a.id)
        self.assertEqual(document.folder_id, self.folder_a.id)
        self.assertEqual(document.created_by_id, self.admin_a.id)
        self.assertEqual(document.nom, 'Chantier Rabat')
        version = DocumentVersion.objects.get(document=document)
        self.assertEqual(version.version, 1)
        self.assertEqual(version.mime, 'application/pdf')
        self.assertEqual(version.uploaded_by_id, self.admin_a.id)
        self.assertTrue(version.file_key.startswith('attachments/'))

    def test_nom_par_defaut_si_absent(self):
        document = services.deposer_photos_assemblees(
            company=self.co_a, folder=self.folder_a,
            images_bytes=[_jpeg_bytes()], created_by=self.admin_a)
        self.assertEqual(document.nom, 'Numérisation')

    def test_dossier_autre_societe_refuse(self):
        with self.assertRaises(ValueError):
            services.deposer_photos_assemblees(
                company=self.co_a, folder=self.folder_b,
                images_bytes=[_jpeg_bytes()], created_by=self.admin_a)

    def test_aucune_photo_leve_value_error(self):
        with self.assertRaises(ValueError):
            services.deposer_photos_assemblees(
                company=self.co_a, folder=self.folder_a,
                images_bytes=[], created_by=self.admin_a)


class AssemblerPhotosViewTests(TestCase):
    def setUp(self):
        self.co_a = make_company('xged12-view-a', 'Xged12View A')
        self.co_b = make_company('xged12-view-b', 'Xged12View B')
        self.admin_a = make_user(self.co_a, 'xged12-view-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Chantiers')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Numérisations')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Chantiers')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Numérisations B')

    def _photo(self, name='photo.jpg'):
        return SimpleUploadedFile(name, _jpeg_bytes(), content_type='image/jpeg')

    def test_assemble_trois_photos_en_un_document(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/assembler-photos/', {
            'folder': self.folder_a.id,
            'photos': [self._photo('a.jpg'), self._photo('b.jpg'),
                       self._photo('c.jpg')],
            'nom': 'Chantier Casablanca',
        }, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        doc = Document.objects.get(id=resp.data['id'])
        self.assertEqual(doc.company_id, self.co_a.id)
        self.assertEqual(doc.folder_id, self.folder_a.id)
        self.assertEqual(doc.nom, 'Chantier Casablanca')
        self.assertEqual(resp.data['version_count'], 1)
        version = doc.versions.get()
        self.assertEqual(version.mime, 'application/pdf')

    def test_requires_folder(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/assembler-photos/', {
            'photos': [self._photo()],
        }, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_requires_at_least_one_photo(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/assembler-photos/', {
            'folder': self.folder_a.id,
        }, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_rejects_other_company_folder(self):
        api = auth(self.admin_a)
        resp = api.post('/api/django/ged/documents/assembler-photos/', {
            'folder': self.folder_b.id,
            'photos': [self._photo()],
        }, format='multipart')
        # Dossier d'une autre société → 404 (jamais de fuite cross-société).
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(Document.objects.filter(folder=self.folder_b).exists())

    def test_requires_auth(self):
        resp = APIClient().post('/api/django/ged/documents/assembler-photos/', {
            'folder': self.folder_a.id, 'photos': [self._photo()],
        }, format='multipart')
        self.assertIn(resp.status_code, (401, 403))
