"""XSAV5 — SLA en jours ouvrés + pause « en attente client ».

Couvre :
  * OFF (défaut) : sla_due_at calendaire, byte-identique à avant XSAV5 ;
  * ON : sla_due_at saute le week-end (jours ouvrés via core.calendar) ;
  * pause 3 jours → échéance effective décalée de 3 jours ;
  * idempotence des actions attente-client / reprendre ;
  * cross-tenant 404 ; migration additive (défauts OFF/0).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav5 -v 2
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import SavSlaSettings, Ticket

User = get_user_model()


def make_company(slug='sav-xsav5', nom='Sav Co XSAV5'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV5WorkingDaysSlaTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xsav5_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav5-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV5', client=self.client_obj)

    def test_off_par_defaut_calcul_calendaire_inchange(self):
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.sla_resolution_days = 3
        sla.save(update_fields=['sla_breach_enabled', 'sla_resolution_days'])
        self.assertFalse(sla.sla_jours_ouvres)

        # Vendredi 2024-05-03 + 3 jours calendaires = lundi 2024-05-06.
        resp = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'date_ouverture': '2024-05-03',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['sla_due_at'], '2024-05-06')

    def test_on_saute_le_weekend(self):
        sla = SavSlaSettings.get(self.company)
        sla.sla_breach_enabled = True
        sla.sla_resolution_days = 3
        sla.sla_jours_ouvres = True
        sla.save(update_fields=[
            'sla_breach_enabled', 'sla_resolution_days', 'sla_jours_ouvres'])

        # Vendredi 2024-05-03 + 3 jours OUVRÉS = mercredi 2024-05-08
        # (lun 06, mar 07, mer 08 — sam/dim sautés).
        resp = self.api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'date_ouverture': '2024-05-03',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['sla_due_at'], '2024-05-08')


class XSAV5PauseTest(TestCase):
    def setUp(self):
        self.company = make_company(slug='sav-xsav5-pause')
        self.user = User.objects.create_user(
            username='xsav5_pause_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav5-pause-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV5-P', client=self.client_obj)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV5-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF,
            sla_due_at=date(2024, 6, 10), created_by=self.user)

    def test_pause_3_jours_decale_echeance_de_3_jours(self):
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/attente-client/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['en_attente_client'])

        self.ticket.refresh_from_db()
        today = self.ticket.attente_depuis + timedelta(days=3)
        # Reprise 3 jours plus tard (date injectée).
        self.ticket.reprendre_apres_attente(today=today)
        self.ticket.save(update_fields=[
            'en_attente_client', 'attente_depuis', 'jours_pause'])
        self.assertEqual(self.ticket.jours_pause, 3)
        self.assertEqual(
            self.ticket.sla_due_at_effectif(), date(2024, 6, 13))

    def test_idempotent_attente_deux_fois(self):
        resp1 = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/attente-client/',
            {}, format='json')
        depuis1 = resp1.data['attente_depuis']
        resp2 = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/attente-client/',
            {}, format='json')
        self.assertEqual(resp2.data['attente_depuis'], depuis1)

    def test_reprendre_sans_pause_active_no_op(self):
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/reprendre/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['jours_pause'], 0)

    def test_off_sans_pause_echeance_effective_egale_brute(self):
        self.assertEqual(
            self.ticket.sla_due_at_effectif(), self.ticket.sla_due_at)

    def test_cross_tenant_404(self):
        other = make_company(slug='sav-xsav5-other', nom='Other Co')
        other_user = User.objects.create_user(
            username='xsav5_other', password='x', role_legacy='admin',
            company=other)
        other_api = auth(other_user)
        resp = other_api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/attente-client/',
            {}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_migration_defauts_off(self):
        other = make_company(slug='sav-xsav5-mig', nom='Sav Co XSAV5 Mig')
        sla = SavSlaSettings.get(other)
        self.assertFalse(sla.sla_jours_ouvres)
        t = Ticket.objects.create(
            company=other, reference='SAV-XSAV5-MIG-1',
            client=Client.objects.create(
                company=other, nom='X', prenom='Y', email='xy@example.invalid'),
            type=Ticket.Type.CORRECTIF, created_by=self.user)
        self.assertFalse(t.en_attente_client)
        self.assertEqual(t.jours_pause, 0)

    def test_pause_ignoree_dans_breach_pendant_attente(self):
        """Un ticket en pause dont l'échéance brute est aujourd'hui ne doit
        pas basculer en breach tant que la pause absorbe le retard."""
        self.ticket.statut = Ticket.Statut.EN_COURS
        self.ticket.sla_due_at = timezone.localdate() - timedelta(days=1)
        self.ticket.en_attente_client = True
        self.ticket.attente_depuis = timezone.localdate() - timedelta(days=5)
        self.ticket.save(update_fields=[
            'statut', 'sla_due_at', 'en_attente_client', 'attente_depuis'])
        self.ticket.recompute_sla_breach()
        self.assertFalse(self.ticket.sla_breach)
