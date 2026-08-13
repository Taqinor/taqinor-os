"""NTCRM29 — Widget "portefeuille de comptes" par commercial.

Critère d'acceptation : la carte liste les comptes du commercial connecté
triés par score, sans fuite cross-tenant ni cross-commercial.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, Lead, PlanCompte
from apps.crm.selectors import portefeuille_commercial
from apps.roles.models import Role

User = get_user_model()


class PortefeuilleCommercialSelectorTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor NTCRM29', slug='taqinor-ntcrm29')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer'])
        self.com1 = User.objects.create_user(
            username='com1_ntcrm29', password='x', company=self.company, role=self.role)
        self.com2 = User.objects.create_user(
            username='com2_ntcrm29', password='x', company=self.company, role=self.role)

        self.client_a = Client.objects.create(company=self.company, nom='Compte A')
        self.client_b = Client.objects.create(company=self.company, nom='Compte B')
        Lead.objects.create(
            company=self.company, nom='Lead A', owner=self.com1, client=self.client_a)
        Lead.objects.create(
            company=self.company, nom='Lead B', owner=self.com2, client=self.client_b)
        PlanCompte.objects.create(company=self.company, client=self.client_a)

    def test_liste_uniquement_les_comptes_du_commercial(self):
        resultats = portefeuille_commercial(self.company, self.com1)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]['client_id'], self.client_a.id)
        self.assertEqual(resultats[0]['plan_compte_id'] is not None, True)

    def test_pas_de_fuite_cross_commercial(self):
        resultats_com2 = portefeuille_commercial(self.company, self.com2)
        client_ids = [r['client_id'] for r in resultats_com2]
        self.assertNotIn(self.client_a.id, client_ids)
        self.assertIn(self.client_b.id, client_ids)

    def test_pas_de_fuite_cross_tenant(self):
        autre = Company.objects.create(nom='Autre NTCRM29', slug='autre-ntcrm29')
        role_autre = Role.objects.create(
            company=autre, nom='Commercial', permissions=['crm_creer'])
        com_autre = User.objects.create_user(
            username='com_autre_ntcrm29', password='x', company=autre, role=role_autre)
        resultats = portefeuille_commercial(autre, com_autre)
        self.assertEqual(resultats, [])


class PortefeuilleCommercialEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor NTCRM29 API', slug='taqinor-ntcrm29-api')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial', permissions=['crm_creer'])
        self.com1 = User.objects.create_user(
            username='com1_ntcrm29_api', password='x', company=self.company, role=self.role)
        self.client_a = Client.objects.create(company=self.company, nom='Compte API')
        Lead.objects.create(
            company=self.company, nom='Lead API', owner=self.com1, client=self.client_a)
        self.api = APIClient()
        self.api.force_authenticate(self.com1)

    def test_endpoint_mon_portefeuille(self):
        resp = self.api.get('/api/django/crm/clients/mon-portefeuille/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['client_id'], self.client_a.id)
