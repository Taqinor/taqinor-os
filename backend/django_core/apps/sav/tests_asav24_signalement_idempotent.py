"""ASAV24 — le signalement public par QR est idempotent : un rejeu identique
(même équipement, même description, fenêtre de quelques minutes) renvoie la
référence existante sans créer de ticket.

Run :
    python manage.py test apps.sav.tests_asav24_signalement_idempotent -v2
"""
from django.core.cache import cache
from django.test import TestCase
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
