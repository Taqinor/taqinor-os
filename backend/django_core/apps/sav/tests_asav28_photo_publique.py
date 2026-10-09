"""ASAV28 — la photo du signalement public par QR est validée AVANT la
création du ticket : format ou taille refusés = 400 sous ``photo``, sans
ticket. Seul le client MinIO (stockage externe) est mocké.

Run :
    python manage.py test apps.sav.tests_asav28_photo_publique -v2
"""
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.records.models import Attachment
from apps.sav.models import Equipement, Ticket
from apps.stock.models import Produit

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
GIF = b'GIF89a' + b'\x00' * 32
HEIC = b'\x00\x00\x00\x18ftypheic' + b'\x00' * 32


class PhotoPubliqueTests(TestCase):

    def setUp(self):
        cache.clear()
        self.company, _ = Company.objects.get_or_create(
            slug='asav28-co', defaults={'nom': 'ASAV28 Co'})
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV28')
        inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV28', client=client)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASAV28',
            prix_achat=0, prix_vente=100)
        self.equip = Equipement.objects.create(
            company=self.company, produit=produit, installation=inst)
        token = self.equip.ensure_public_token()
        self.url = f'/api/django/public/sav/equipement/{token}/signaler/'
        self.api = APIClient()
        self._patchs = [
            mock.patch('apps.records.storage.get_minio_client'),
            mock.patch('apps.records.storage.ensure_uploads_bucket'),
        ]
        for p in self._patchs:
            p.start()
            self.addCleanup(p.stop)

    def _post(self, nom, contenu, description='Panne photo'):
        return self.api.post(
            self.url,
            {'description': description,
             'photo': SimpleUploadedFile(nom, contenu)},
            format='multipart')

    def _nb(self):
        return (Ticket.objects.filter(equipement=self.equip).count(),
                Attachment.objects.filter(company=self.company).count())

    def test_png_joint(self):
        r = self._post('photo.png', PNG)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self._nb(), (1, 1))

    def test_gif_400_sans_ticket(self):
        r = self._post('photo.gif', GIF)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('photo', r.data)
        self.assertEqual(self._nb(), (0, 0))

    def test_heic_400_sans_ticket(self):
        r = self._post('photo.heic', HEIC)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('photo', r.data)
        self.assertEqual(self._nb(), (0, 0))

    def test_trop_gros_400_sans_ticket(self):
        r = self._post('gros.png', PNG + b'\x00' * (10 * 1024 * 1024))
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(self._nb(), (0, 0))

    def test_retry_apres_refus_cree_le_ticket(self):
        self._post('photo.gif', GIF, description='Même panne')
        r = self._post('photo.png', PNG, description='Même panne')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self._nb(), (1, 1))
