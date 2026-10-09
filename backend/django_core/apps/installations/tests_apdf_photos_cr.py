"""APDF37 (C-APDF-012) — le PDF du compte-rendu d'intervention EMBARQUE les
photos jointes (octets lus côté serveur, réduits par Pillow, data URI, nombre
et poids plafonnés) ; le PDF public est le même.

Seule la lecture de l'objet stocké (MinIO) est remplacée par un faux
(frontière externe) ; le rendu WeasyPrint est réel.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_apdf_photos_cr"
"""
import io
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company

from apps.installations import field_services, intervention_pdf
from apps.installations.models import Installation, Intervention
from apps.records.models import Attachment

User = get_user_model()


def _jpeg(couleur):
    from PIL import Image
    sortie = io.BytesIO()
    Image.new('RGB', (1600, 1200), couleur).save(sortie, format='JPEG')
    return sortie.getvalue()


def _compter_images(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    return sum(len(page.get_images()) for page in doc)


class PhotosCompteRenduPdfTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-apdf37', defaults={'nom': 'Co APDF37'})
        self.user = User.objects.create_user(
            username='resp-apdf37', password='x', company=self.company,
            role_legacy='responsable')
        inst = Installation.objects.create(
            company=self.company, reference='CH-APDF37')
        self.iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user, statut=Intervention.Statut.VALIDEE)
        field_services.seed_shotlist_slots(self.company)
        self.slot = next(
            s for s in field_services.active_shotlist(self.company)
            if s.phase == 'avant')
        self.ct = ContentType.objects.get_for_model(Intervention)

    def _photo(self, n):
        return Attachment.objects.create(
            company=self.company, content_type=self.ct, object_id=self.iv.id,
            file_key=f'k/apdf37/{n}', mime='image/jpeg',
            filename=field_services.encode_slot_filename(
                self.slot.cle, f'p{n}.jpg'),
            uploaded_by=self.user)

    def _fake_fetch(self, key):
        return _jpeg((200, 30, 30)), None

    def test_images_embarquees(self):
        self._photo(1)
        self._photo(2)
        with mock.patch('apps.records.storage.fetch_attachment',
                        self._fake_fetch):
            pdf = intervention_pdf.compte_rendu_pdf(self.iv)
        self.assertEqual(_compter_images(pdf), 2)

    def test_pdf_public_images(self):
        self._photo(1)
        self._photo(2)
        token = self.iv.ensure_lien_rapport_token()
        with mock.patch('apps.records.storage.fetch_attachment',
                        self._fake_fetch):
            r = self.client.get(
                f'/api/django/public/installations/intervention-rapport/'
                f'{token}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(_compter_images(r.content), 2)

    def test_plafond(self):
        for n in range(intervention_pdf.PDF_PHOTOS_MAX + 2):
            self._photo(n)
        with mock.patch('apps.records.storage.fetch_attachment',
                        self._fake_fetch):
            groupes, non_reproduites = (
                intervention_pdf._photos_payload_embarquees(self.iv))
        retenues = sum(len(v) for v in groupes.values())
        self.assertEqual(retenues, intervention_pdf.PDF_PHOTOS_MAX)
        self.assertEqual(non_reproduites, 2)
        with mock.patch('apps.records.storage.fetch_attachment',
                        self._fake_fetch):
            pdf = intervention_pdf.compte_rendu_pdf(self.iv)
        import fitz
        texte = ''.join(p.get_text() for p in fitz.open(
            stream=pdf, filetype='pdf'))
        self.assertIn('2 photos non reproduites', texte)
