"""ZSAL4 — Assistant de conversion lead→client explicite (nouveau / lier /
aucun), mirroir de l'action Odoo « Convert to Opportunity ».

Covers:
  - mode 'lier' rattache le bon client existant, borné société (cross-company
    -> 404 via l'API, ValueError via le service).
  - mode 'nouveau' crée un client sans en doubler un déjà lié (réutilise
    strictement resolve_client_for_lead).
  - mode 'aucun' ne crée rien, marque juste le lead qualifié.
  - Le chatter (LeadActivity) trace chaque choix.
  - Scoping multi-tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead, LeadActivity
from apps.crm.services import convertir_lead_en_client

User = get_user_model()


def make_company(slug='zsal4-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


class TestConvertirLeadEnClientService(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='zsal4resp', password='x', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='Test',
            email='lead@example.ma', telephone='+212600000002')

    def test_mode_lier_rattache_client_existant(self):
        client = Client.objects.create(company=self.company, nom='Existant')
        result = convertir_lead_en_client(
            lead=self.lead, user=self.user, mode='lier', client_id=client.id)
        self.assertEqual(result, client)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.client_id, client.id)
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=self.lead, body__icontains='client existant lié').exists())

    def test_mode_lier_client_autre_societe_leve_erreur(self):
        autre = make_company('zsal4-autre')
        client_autre = Client.objects.create(company=autre, nom='Ailleurs')
        with self.assertRaises(ValueError):
            convertir_lead_en_client(
                lead=self.lead, user=self.user, mode='lier',
                client_id=client_autre.id)

    def test_mode_lier_sans_client_id_leve_erreur(self):
        with self.assertRaises(ValueError):
            convertir_lead_en_client(lead=self.lead, user=self.user, mode='lier')

    def test_mode_nouveau_cree_client(self):
        client = convertir_lead_en_client(
            lead=self.lead, user=self.user, mode='nouveau')
        self.assertIsNotNone(client)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.client_id, client.id)
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=self.lead, body__icontains='nouveau client').exists())

    def test_mode_nouveau_ne_double_pas_client_deja_lie(self):
        client_deja_lie = Client.objects.create(company=self.company, nom='Déjà lié')
        self.lead.client = client_deja_lie
        self.lead.save(update_fields=['client'])
        nb_avant = Client.objects.filter(company=self.company).count()
        result = convertir_lead_en_client(
            lead=self.lead, user=self.user, mode='nouveau')
        self.assertEqual(result, client_deja_lie)
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), nb_avant)

    def test_mode_aucun_ne_cree_rien(self):
        nb_avant = Client.objects.filter(company=self.company).count()
        result = convertir_lead_en_client(
            lead=self.lead, user=self.user, mode='aucun')
        self.assertIsNone(result)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.client_id)
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), nb_avant)
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=self.lead, body__icontains='qualifié SANS client').exists())

    def test_mode_invalide_leve_erreur(self):
        with self.assertRaises(ValueError):
            convertir_lead_en_client(lead=self.lead, user=self.user, mode='bidon')


class TestConvertirClientAPI(TestCase):
    def setUp(self):
        self.company = make_company('zsal4-api-co')
        self.other_company = make_company('zsal4-api-other')
        self.user = User.objects.create_user(
            username='zsal4apiuser', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(company=self.company, nom='Lead API')
        self.api = APIClient()
        token = AccessToken.for_user(self.user)
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_convertir_lier_happy_path(self):
        client = Client.objects.create(company=self.company, nom='C')
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/convertir-client/',
            {'mode': 'lier', 'client_id': client.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['client']['id'], client.id)

    def test_convertir_lier_client_autre_societe_400(self):
        client_autre = Client.objects.create(company=self.other_company, nom='Ailleurs')
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/convertir-client/',
            {'mode': 'lier', 'client_id': client_autre.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_convertir_aucun_happy_path(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/convertir-client/',
            {'mode': 'aucun'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNone(resp.data['client'])
