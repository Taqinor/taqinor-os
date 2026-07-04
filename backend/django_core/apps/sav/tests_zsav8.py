"""ZSAV8 — Convertir un ticket en opportunité CRM.

Couvre :
  * `POST tickets/{id}/creer-lead/` crée un lead CRM au stade NEW (STAGES.py)
    lié au client du ticket, et pose `Ticket.lead_id_ext` ;
  * un lead OUVERT (stage != COLD) déjà lié à ce client est RÉUTILISÉ plutôt
    que dupliqué (idempotence) ;
  * un lead COLD du même client n'empêche pas la création d'un nouveau lead ;
  * cross-tenant : un ticket d'une autre société renvoie 404.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zsav8 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.crm import stages
from apps.sav.models import Ticket

User = get_user_model()


def make_company(slug='sav-zsav8', nom='Sav Co ZSAV8'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZSAV8CreerLeadTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zsav8_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            telephone='0611223344', email='zsav8-client@example.invalid')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ZSAV8-1',
            client=self.client_obj, type=Ticket.Type.CORRECTIF,
            description='Onduleur en fin de vie, upsell possible',
            created_by=self.admin)

    def test_creer_lead_stade_new_lie_au_client(self):
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/creer-lead/')
        self.assertEqual(resp.status_code, 201, resp.content)
        lead = Lead.objects.get(pk=resp.data['lead_id'])
        self.assertEqual(lead.stage, stages.NEW)
        self.assertEqual(lead.client_id, self.client_obj.id)

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.lead_id_ext, lead.id)

    def test_reutilise_lead_ouvert_existant(self):
        lead_existant = Lead.objects.create(
            company=self.company, nom='Client Test', client=self.client_obj,
            stage=stages.CONTACTED)
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/creer-lead/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['lead_id'], lead_existant.id)
        self.assertEqual(
            Lead.objects.filter(client=self.client_obj).count(), 1)

    def test_lead_cold_du_meme_client_nempeche_pas_creation(self):
        Lead.objects.create(
            company=self.company, nom='Client Test', client=self.client_obj,
            stage=stages.COLD)
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/creer-lead/')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(
            Lead.objects.filter(client=self.client_obj).count(), 2)

    def test_appel_repete_idempotent_meme_lead(self):
        api = auth(self.admin)
        resp1 = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/creer-lead/')
        resp2 = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/creer-lead/')
        self.assertEqual(resp1.data['lead_id'], resp2.data['lead_id'])
        self.assertEqual(
            Lead.objects.filter(client=self.client_obj).count(), 1)

    def test_cross_tenant_404(self):
        other_company = make_company('sav-zsav8-other', 'Autre Co ZSAV8')
        other_admin = User.objects.create_user(
            username='zsav8_other_admin', password='x', role_legacy='admin',
            company=other_company)
        api = auth(other_admin)
        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/creer-lead/')
        self.assertEqual(resp.status_code, 404, resp.content)
