"""ACRM38 (C-ACRM-033) — les clés d'identité de ``resolve_client_for_lead``
sont celles de la dédup.

Sondes V_VB LSVC2-1 / LSVC2-2 / LSVC2-8 : (a) deux leads à e-mail ``""``
(API) → ``IntegrityError`` au second client ; (b) ``'A@X.ma '`` contre un
client ``'a@x.ma'`` → un doublon ; (c) deux personnes à e-mail Meta ``' '``
→ un client PARTAGÉ ; (d) un téléphone long (tronqué à 20 au stockage) →
deux clients. Désormais : e-mail normalisé ou NULL, téléphone comparé sur la
valeur stockée, e-mail Meta nettoyé.

Services réels ; aucun mock.
"""
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.crm.services import create_lead_from_meta_lead_ads
from apps.crm.clients_identite import resolve_client_for_lead


class IdentiteClientTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM38 Solaire', slug='acrm38-identite')

    def _lead(self, **champs):
        lead = Lead.objects.create(company=self.company, nom='Personne')
        Lead.objects.filter(pk=lead.pk).update(**champs)
        return Lead.objects.get(pk=lead.pk)

    def test_email_vide_pas_d_erreur(self):
        un = self._lead(email='', telephone='0612000001')
        deux = self._lead(email='', telephone='0612000002')
        c1 = resolve_client_for_lead(un)
        c2 = resolve_client_for_lead(deux)
        self.assertNotEqual(c1.pk, c2.pk)
        for client in (c1, c2):
            client.refresh_from_db()
            self.assertIsNone(client.email)

    def test_espaces_meme_client(self):
        existant = Client.objects.create(
            company=self.company, nom='Alaoui', email='a@x.ma')
        lead = self._lead(email='A@X.ma ')
        self.assertEqual(resolve_client_for_lead(lead).pk, existant.pk)
        self.assertEqual(Client.objects.filter(company=self.company).count(),
                         1)

    def test_blanc_jamais_partage(self):
        leads = [create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id=f'ACRM38-{i}',
            field_data=[
                {'name': 'full_name', 'values': [f'Personne {i}']},
                {'name': 'email', 'values': [' ']},
                {'name': 'phone_number', 'values': [f'+21266138000{i}']},
            ]) for i in (1, 2)]
        clients = [resolve_client_for_lead(le) for le in leads]
        self.assertNotEqual(clients[0].pk, clients[1].pk)
        for lead in leads:
            lead.refresh_from_db()
            self.assertIn(lead.email, (None, ''))

    def test_telephone_long_un_client(self):
        long = '+212 6 12 34 56 78 / 05 22 00 00 00'
        un = self._lead(email=None, telephone=long)
        deux = self._lead(email=None, telephone=long)
        self.assertEqual(resolve_client_for_lead(un).pk,
                         resolve_client_for_lead(deux).pk)
        self.assertEqual(Client.objects.filter(company=self.company).count(),
                         1)
