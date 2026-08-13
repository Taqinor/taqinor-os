"""NTCRM18 — Journal de consultation (`SalleVenteVue`) de la salle de vente
publique : chaque visite réussie (sans authentification) est journalisée."""
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, SalleVente, SalleVenteVue


class SalleVenteVueTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM18', slug='taqinor-ntcrm18')
        self.client_obj = Client.objects.create(company=self.company, nom='Client SV18')
        self.salle = SalleVente.objects.create(
            company=self.company, client=self.client_obj, titre='Salle publique')

    def test_chaque_visite_reussie_est_journalisee_sans_auth(self):
        anon = APIClient()  # aucune authentification
        for _ in range(3):
            resp = anon.get(f'/api/django/crm/salle-vente/{self.salle.token}/')
            self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            SalleVenteVue.objects.filter(salle=self.salle).count(), 3)

    def test_ip_jamais_stockee_en_clair(self):
        anon = APIClient()
        resp = anon.get(
            f'/api/django/crm/salle-vente/{self.salle.token}/',
            REMOTE_ADDR='203.0.113.7')
        self.assertEqual(resp.status_code, 200)
        vue = SalleVenteVue.objects.get(salle=self.salle)
        self.assertNotEqual(vue.ip_hash, '203.0.113.7')
        self.assertTrue(vue.ip_hash)

    def test_visite_refusee_ne_journalise_pas(self):
        anon = APIClient()
        resp = anon.get('/api/django/crm/salle-vente/jeton-inconnu/')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(SalleVenteVue.objects.count(), 0)
