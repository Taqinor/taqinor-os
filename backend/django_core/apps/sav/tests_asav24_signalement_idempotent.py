"""ASAV24 — le signalement public par QR est idempotent : un rejeu identique
(même équipement, même description, fenêtre de quelques minutes) renvoie la
référence existante sans créer de ticket.

Run :
    python manage.py test apps.sav.tests_asav24_signalement_idempotent -v2
"""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement, Ticket
from apps.stock.models import Produit


class SignalementIdempotentTests(TestCase):

    def setUp(self):
        cache.clear()
        self.company, _ = Company.objects.get_or_create(
            slug='asav24-co', defaults={'nom': 'ASAV24 Co'})
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV24')
        inst = Installation.objects.create(
            company=self.company, reference='CHT-ASAV24', client=client)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ASAV24',
            prix_achat=0, prix_vente=100)
        self.equip = Equipement.objects.create(
            company=self.company, produit=produit, installation=inst)
        self.client_obj, self.inst = client, inst
        self.token = self.equip.ensure_public_token()
        self.api = APIClient()
        self.url = f'/api/django/public/sav/equipement/{self.token}/signaler/'

    def _nb(self):
        return Ticket.objects.filter(equipement=self.equip).count()

    def test_rejeu_meme_reference(self):
        r1 = self.api.post(self.url, {'description': 'Onduleur bip'})
        r2 = self.api.post(self.url, {'description': 'Onduleur bip'})
        self.assertEqual(r1.status_code, 201, r1.content)
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertEqual(r1.data['reference'], r2.data['reference'])
        self.assertEqual(self._nb(), 1)

    def test_description_differente(self):
        r1 = self.api.post(self.url, {'description': 'Onduleur bip'})
        r3 = self.api.post(self.url, {'description': 'Écran noir'})
        self.assertEqual(r3.status_code, 201, r3.content)
        self.assertNotEqual(r1.data['reference'], r3.data['reference'])
        self.assertEqual(self._nb(), 2)

    def _ancien(self, texte):
        """Ticket de J-30 au même texte sur l'équipement."""
        ancien = Ticket.objects.create(
            company=self.company, reference='ANCIEN-A106',
            client=self.client_obj, installation=self.inst,
            equipement=self.equip, type=Ticket.Type.CORRECTIF,
            description=texte,
            date_ouverture=timezone.localdate() - timedelta(days=30))
        Ticket.objects.filter(pk=ancien.pk).update(
            date_creation=timezone.now() - timedelta(days=30))
        return ancien

    def test_refus_photo_puis_renvoi_cree(self):
        """ASAV106 — la photo refusée (HEIC, 400) ne consomme pas la clé
        anti-rejeu : le renvoi sans photo crée un NOUVEAU ticket."""
        ancien = self._ancien('Onduleur bip')
        heic = b'\x00\x00\x00\x18ftypheic' + b'\x00' * 32
        with mock.patch('apps.records.storage.get_minio_client'), \
                mock.patch('apps.records.storage.ensure_uploads_bucket'):
            r1 = self.api.post(self.url, {
                'description': 'Onduleur bip',
                'photo': SimpleUploadedFile('photo.heic', heic)},
                format='multipart')
            r2 = self.api.post(self.url, {'description': 'Onduleur bip'},
                               format='multipart')
        self.assertEqual(r1.status_code, 400, r1.content)
        self.assertIn('photo', r1.data)
        self.assertEqual(r2.status_code, 201, r2.content)
        self.assertNotEqual(r2.data['reference'], ancien.reference)
        refs = set(Ticket.objects.filter(equipement=self.equip)
                   .values_list('reference', flat=True))
        self.assertEqual(refs, {ancien.reference, r2.data['reference']})

    def test_cle_perdue_ne_rend_pas_un_ancien_ticket(self):
        """ASAV106 — clé de la fenêtre déjà prise : seul un ticket de CETTE
        fenêtre au même texte est rendu, jamais un ticket ancien."""
        ancien = self._ancien('Onduleur bip')
        with mock.patch('core.idempotency.dedupe_event', return_value=False):
            r = self.api.post(self.url, {'description': 'Onduleur bip'})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotEqual(r.data['reference'], ancien.reference)
        self.assertEqual(self._nb(), 2)
