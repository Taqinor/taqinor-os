"""ACRM40 (C-ACRM-035) — la fusion de deux leads ayant CHACUN leur fiche
client le dit.

Sonde V_VB LSVC2-7 : le survivant gardait son client K1, les devis de
l'absorbé restaient rattachés à K2, et AUCUNE note ne mentionnait K2. Désormais
une ligne de chatter du survivant nomme K1 (gardée), K2 et les références
des devis restés sur K2, et la réponse de fusion porte
``clients_distincts: [K1, K2]``. La fusion des clients reste humaine.

POST de fusion réel ; aucun mock.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead, LeadActivity
from apps.ventes.models import Devis

User = get_user_model()


class FusionDeuxClientsTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM40 Solaire', slug='acrm40-clients')
        self.user = User.objects.create_user(
            username='acrm40-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.k1 = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='K1')
        self.k2 = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='K2')
        self.survivant = Lead.objects.create(
            company=self.company, nom='Alaoui', owner=self.user,
            client=self.k1, telephone='+212661404040')
        self.absorbe = Lead.objects.create(
            company=self.company, nom='Alaoui', owner=self.user,
            client=self.k2, telephone='+212661404040')
        self.devis_k2 = Devis.objects.create(
            company=self.company, reference='DEV-ACRM40-K2', client=self.k2,
            lead=self.absorbe, statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))

    def _fusionner(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.survivant.pk}/merge/',
            {'others': [self.absorbe.pk]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp

    def test_note_deux_clients(self):
        resp = self._fusionner()
        self.survivant.refresh_from_db()
        self.assertEqual(self.survivant.client_id, self.k1.pk)
        self.assertEqual(resp.data['clients_distincts'],
                         [self.k1.pk, self.k2.pk])
        notes = list(LeadActivity.objects.filter(
            lead=self.survivant, body__startswith='Deux fiches client'
        ).values_list('body', flat=True))
        self.assertEqual(len(notes), 1, notes)
        self.assertIn(f'#{self.k1.pk}', notes[0])
        self.assertIn(f'#{self.k2.pk}', notes[0])
        self.assertIn('DEV-ACRM40-K2', notes[0])

    def test_un_client_muet(self):
        Lead.objects.filter(pk=self.absorbe.pk).update(client=None)
        Devis.objects.filter(pk=self.devis_k2.pk).update(client=self.k1)
        resp = self._fusionner()
        self.assertEqual(resp.data['clients_distincts'], [])
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.survivant, body__startswith='Deux fiches client'
        ).exists())
