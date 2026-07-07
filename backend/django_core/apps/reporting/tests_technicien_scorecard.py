"""XFSM17 — scorecard technicien (coaching) vs moyenne équipe."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav.models import Ticket
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/insights/technicien-scorecard/'


class ScorecardBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='xfsm17-co', defaults={'nom': 'XFSM17 Co'})[0]
        self.user = User.objects.create_user(
            username='xfsm17_u', password='x', role_legacy='responsable',
            company=self.company)
        self.tech = User.objects.create_user(
            username='xfsm17_tech', password='x', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ClientXFSM17')
        self.installation = Installation.objects.create(
            company=self.company, reference='CH-XFSM17-1', client=self.client_obj)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _intervention(self, technicien=None, **kwargs):
        defaults = dict(
            company=self.company, installation=self.installation,
            type_intervention=Intervention.Type.DEPANNAGE,
            technicien=technicien or self.tech,
        )
        defaults.update(kwargs)
        return Intervention.objects.create(**defaults)


class TestTechnicienScorecard(ScorecardBase):
    def test_requires_responsable_or_admin(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.tech)}')
        resp = api.get(URL, {'technicien': self.tech.id})
        self.assertEqual(resp.status_code, 403)

    def test_technicien_required(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 400)

    def test_technicien_not_found(self):
        resp = self.api.get(URL, {'technicien': 999999})
        self.assertEqual(resp.status_code, 404)

    def test_scorecard_basic_fields(self):
        self._intervention(statut=Intervention.Statut.TERMINEE)
        self._intervention(statut=Intervention.Statut.PRETE)

        resp = self.api.get(URL, {'technicien': self.tech.id})
        self.assertEqual(resp.status_code, 200)
        sc = resp.data['scorecard']
        self.assertEqual(sc['technicien_id'], self.tech.id)
        self.assertEqual(sc['interventions_total'], 2)
        self.assertEqual(sc['interventions_terminees'], 1)

    def test_recidive_rate_in_scorecard(self):
        Ticket.objects.create(
            company=self.company, reference='T-XFSM17-1', client=self.client_obj,
            technicien_responsable=self.tech, est_recidive=True)
        Ticket.objects.create(
            company=self.company, reference='T-XFSM17-2', client=self.client_obj,
            technicien_responsable=self.tech, est_recidive=False)

        resp = self.api.get(URL, {'technicien': self.tech.id})
        self.assertEqual(resp.status_code, 200)
        sc = resp.data['scorecard']
        self.assertEqual(sc['nb_recidives'], 1)
        self.assertEqual(sc['taux_recidive_pct'], 50.0)

    def test_team_average_present(self):
        other_tech = User.objects.create_user(
            username='xfsm17_tech2', password='x', company=self.company)
        self._intervention(technicien=self.tech, statut=Intervention.Statut.TERMINEE)
        self._intervention(technicien=other_tech, statut=Intervention.Statut.TERMINEE)

        resp = self.api.get(URL, {'technicien': self.tech.id})
        self.assertEqual(resp.status_code, 200)
        moyenne = resp.data['moyenne_equipe']
        self.assertEqual(moyenne['nb_techniciens'], 2)

    def test_no_internal_cost_exposed(self):
        resp = self.api.get(URL, {'technicien': self.tech.id})
        self.assertEqual(resp.status_code, 200)
        payload_str = str(resp.data)
        self.assertNotIn('prix_achat', payload_str)
        self.assertNotIn('cost_estimate', payload_str)
        self.assertNotIn('margin', payload_str)

    def test_multi_tenant_scoping(self):
        other_co = Company.objects.create(slug='xfsm17-other', nom='Autre Co')
        other_tech = User.objects.create_user(
            username='xfsm17_other_tech', password='x', company=other_co)
        resp = self.api.get(URL, {'technicien': other_tech.id})
        self.assertEqual(resp.status_code, 404)

    def test_export_xlsx(self):
        self._intervention(statut=Intervention.Statut.TERMINEE)
        resp = self.api.get(URL, {'technicien': self.tech.id, 'export': 'xlsx'})
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))

    def test_period_filter(self):
        today = date.today()
        self._intervention(
            date_prevue=today - timedelta(days=100),
            statut=Intervention.Statut.TERMINEE)
        resp = self.api.get(URL, {
            'technicien': self.tech.id,
            'from': today.isoformat(),
            'to': today.isoformat(),
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['scorecard']['interventions_total'], 0)
