"""XSAV8 — rapport de conformité SLA + KPI SAV avancés (fixtures datées)."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.sav.models import Ticket
from authentication.models import Company

User = get_user_model()


class SavSlaBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='sav-sla-co', defaults={'nom': 'Sav Sla Co'})[0]
        self.user = User.objects.create_user(
            username='sav_sla_u', password='x', role_legacy='responsable',
            company=self.company)
        self.tech = User.objects.create_user(
            username='tech1', password='x', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ClientSLA')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _make_ticket(self, **kwargs):
        defaults = dict(
            company=self.company, reference=f'T-{Ticket.objects.count() + 1}',
            client=self.client_obj, technicien_responsable=self.tech,
        )
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)


class TestSavSlaCompliance(SavSlaBase):
    def test_pct_first_response_and_resolution_by_priority(self):
        today = date.today()
        # Répondu ET résolu dans les temps.
        t1 = self._make_ticket(
            priorite=Ticket.Priorite.URGENTE,
            statut=Ticket.Statut.CLOTURE,
            sla_due_at=today + timedelta(days=2),
            date_resolution=today,
        )
        Ticket.objects.filter(pk=t1.pk).update(
            date_premiere_reponse=today)
        # Répondu et résolu EN RETARD (sla_due_at dépassé).
        t2 = self._make_ticket(
            priorite=Ticket.Priorite.URGENTE,
            statut=Ticket.Statut.CLOTURE,
            sla_due_at=today - timedelta(days=1),
            date_resolution=today,
        )
        Ticket.objects.filter(pk=t2.pk).update(
            date_premiere_reponse=today)

        resp = self.api.get('/api/django/reporting/insights/sav-sla/')
        self.assertEqual(resp.status_code, 200)
        urgent = next(
            p for p in resp.data['par_priorite'] if p['priorite'] == 'urgente')
        self.assertEqual(urgent['total'], 2)
        self.assertEqual(urgent['pct_premiere_reponse_ok'], 50.0)
        self.assertEqual(urgent['pct_resolution_ok'], 50.0)

    def test_backlog_aged_buckets(self):
        today = date.today()
        recent = self._make_ticket(statut=Ticket.Statut.NOUVEAU)
        Ticket.objects.filter(pk=recent.pk).update(
            date_creation=today)
        mid = self._make_ticket(statut=Ticket.Statut.EN_COURS)
        Ticket.objects.filter(pk=mid.pk).update(
            date_creation=today - timedelta(days=5))
        old = self._make_ticket(statut=Ticket.Statut.PLANIFIE)
        Ticket.objects.filter(pk=old.pk).update(
            date_creation=today - timedelta(days=20))
        # Clôturé -> jamais dans le backlog (pas "ouvert").
        self._make_ticket(statut=Ticket.Statut.CLOTURE)

        resp = self.api.get('/api/django/reporting/insights/sav-sla/')
        self.assertEqual(resp.status_code, 200)
        buckets = resp.data['backlog_vieilli']['buckets']
        self.assertEqual(buckets['0_2j'], 1)
        self.assertEqual(buckets['3_7j'], 1)
        self.assertEqual(buckets['plus_7j'], 1)

    def test_preventif_vs_correctif_ratio(self):
        self._make_ticket(type=Ticket.Type.PREVENTIF)
        self._make_ticket(type=Ticket.Type.PREVENTIF)
        self._make_ticket(type=Ticket.Type.CORRECTIF)
        resp = self.api.get('/api/django/reporting/insights/sav-sla/')
        self.assertEqual(resp.status_code, 200)
        pvc = resp.data['preventif_vs_correctif']
        self.assertEqual(pvc['nb_preventif'], 2)
        self.assertEqual(pvc['nb_correctif'], 1)
        self.assertAlmostEqual(pvc['pct_preventif'], 66.7, places=1)

    def test_visites_preventives_a_heure_vs_retard(self):
        today = date.today()
        a_heure = self._make_ticket(
            type=Ticket.Type.PREVENTIF,
            date_tournee=today, date_resolution=today)
        en_retard = self._make_ticket(
            type=Ticket.Type.PREVENTIF,
            date_tournee=today - timedelta(days=3), date_resolution=today)
        # Sans date_tournee -> exclu (indéterminé).
        self._make_ticket(type=Ticket.Type.PREVENTIF, date_resolution=today)

        resp = self.api.get('/api/django/reporting/insights/sav-sla/')
        self.assertEqual(resp.status_code, 200)
        visites = resp.data['visites_preventives']
        self.assertEqual(visites['total_evaluees'], 2)
        self.assertEqual(visites['a_heure'], 1)
        self.assertEqual(visites['en_retard'], 1)
        self.assertIsNotNone(a_heure)
        self.assertIsNotNone(en_retard)

    def test_healthy_cases_ignored_by_backlog_and_sla(self):
        """Un ticket sain (résolu à temps, non ouvert) n'apparaît pas au
        backlog et compte correctement en conformité."""
        today = date.today()
        t = self._make_ticket(
            statut=Ticket.Statut.CLOTURE,
            sla_due_at=today + timedelta(days=5),
            date_resolution=today,
        )
        Ticket.objects.filter(pk=t.pk).update(date_premiere_reponse=today)
        resp = self.api.get('/api/django/reporting/insights/sav-sla/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(sum(resp.data['backlog_vieilli']['buckets'].values()), 0)

    def test_per_technicien_breakdown(self):
        tech2 = User.objects.create_user(
            username='tech2', password='x', company=self.company)
        today = date.today()
        t1 = self._make_ticket(
            technicien_responsable=self.tech,
            sla_due_at=today + timedelta(days=1), date_resolution=today)
        Ticket.objects.filter(pk=t1.pk).update(date_premiere_reponse=today)
        self._make_ticket(technicien_responsable=tech2)

        resp = self.api.get('/api/django/reporting/insights/sav-sla/')
        self.assertEqual(resp.status_code, 200)
        techs = {t['technicien_id']: t for t in resp.data['par_technicien']}
        self.assertIn(self.tech.id, techs)
        self.assertIn(tech2.id, techs)
        self.assertEqual(techs[self.tech.id]['pct_resolution_ok'], 100.0)

    def test_export_xlsx(self):
        self._make_ticket()
        resp = self.api.get(
            '/api/django/reporting/insights/sav-sla/?export=xlsx')
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))

    def test_gated_to_responsable_or_admin(self):
        limited = User.objects.create_user(
            username='limited_sla', password='x', company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(limited)}')
        resp = api.get('/api/django/reporting/insights/sav-sla/')
        self.assertEqual(resp.status_code, 403)

    def test_filter_by_period_and_technicien(self):
        today = date.today()
        old = self._make_ticket(technicien_responsable=self.tech)
        Ticket.objects.filter(pk=old.pk).update(
            date_creation=today - timedelta(days=100))
        self._make_ticket(technicien_responsable=self.tech)
        resp = self.api.get(
            '/api/django/reporting/insights/sav-sla/'
            f'?from={(today - timedelta(days=5)).isoformat()}'
            f'&technicien={self.tech.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_tickets'], 1)
