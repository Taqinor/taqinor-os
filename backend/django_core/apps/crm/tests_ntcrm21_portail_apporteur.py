"""NTCRM21 — Portail apporteur en lecture seule (tokenisé, sans compte)."""
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Apporteur, DealEnregistre, Lead


class PortailApporteurTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM21', slug='taqinor-ntcrm21')
        self.apporteur1 = Apporteur.objects.create(
            company=self.company, nom='Apporteur Un')
        self.apporteur2 = Apporteur.objects.create(
            company=self.company, nom='Apporteur Deux')
        self.lead1 = Lead.objects.create(
            company=self.company, nom='Client 1', ville='Casablanca')
        self.lead2 = Lead.objects.create(
            company=self.company, nom='Client 2', ville='Rabat')
        self.deal1 = DealEnregistre.objects.create(
            company=self.company, apporteur=self.apporteur1, lead=self.lead1)
        self.deal2 = DealEnregistre.objects.create(
            company=self.company, apporteur=self.apporteur2, lead=self.lead2)

    def test_apporteur_voit_uniquement_ses_propres_deals(self):
        anon = APIClient()
        resp = anon.get(
            f'/api/django/crm/apporteur-portail/{self.apporteur1.token_acces}/mes-deals/')
        self.assertEqual(resp.status_code, 200, resp.data)
        deal_ids = [d['id'] for d in resp.data['deals']]
        self.assertIn(self.deal1.id, deal_ids)
        self.assertNotIn(self.deal2.id, deal_ids)

    def test_ne_montre_que_nom_ville_du_client(self):
        anon = APIClient()
        resp = anon.get(
            f'/api/django/crm/apporteur-portail/{self.apporteur1.token_acces}/mes-deals/')
        deal = resp.data['deals'][0]
        self.assertEqual(deal['client_nom'], 'Client 1')
        self.assertEqual(deal['client_ville'], 'Casablanca')
        self.assertNotIn('client_telephone', deal)
        self.assertNotIn('client_email', deal)

    def test_jeton_inconnu_404(self):
        anon = APIClient()
        resp = anon.get('/api/django/crm/apporteur-portail/jeton-inconnu/mes-deals/')
        self.assertEqual(resp.status_code, 404)

    def test_apporteur_inactif_404(self):
        self.apporteur1.actif = False
        self.apporteur1.save(update_fields=['actif'])
        anon = APIClient()
        resp = anon.get(
            f'/api/django/crm/apporteur-portail/{self.apporteur1.token_acces}/mes-deals/')
        self.assertEqual(resp.status_code, 404)
