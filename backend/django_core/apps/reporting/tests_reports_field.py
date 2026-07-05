"""XFSM16 — rapport analytics field service (FTF, MTTR, ponctualité, récidive)."""
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.sav.models import Ticket
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/reports/field/'


class FieldReportBase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='xfsm16-co', defaults={'nom': 'XFSM16 Co'})[0]
        self.user = User.objects.create_user(
            username='xfsm16_u', password='x', role_legacy='responsable',
            company=self.company)
        self.tech = User.objects.create_user(
            username='xfsm16_tech', password='x', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ClientXFSM16')
        self.installation = Installation.objects.create(
            company=self.company, reference='CH-XFSM16-1', client=self.client_obj)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _ticket(self, **kwargs):
        defaults = dict(
            company=self.company, reference=f'T-XFSM16-{Ticket.objects.count() + 1}',
            client=self.client_obj, technicien_responsable=self.tech,
        )
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)

    def _intervention(self, **kwargs):
        defaults = dict(
            company=self.company, installation=self.installation,
            type_intervention=Intervention.Type.DEPANNAGE,
            technicien=self.tech,
        )
        defaults.update(kwargs)
        return Intervention.objects.create(**defaults)


class TestFieldServiceReport(FieldReportBase):
    def test_requires_responsable_or_admin(self):
        limited = User.objects.create_user(
            username='xfsm16_limited', password='x', company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(limited)}')
        resp = api.get(URL)
        self.assertEqual(resp.status_code, 403)

    def test_first_time_fix_rate(self):
        today = date.today()
        # Résolu en UNE seule intervention → FTF.
        t1 = self._ticket(date_resolution=today)
        self._intervention(ticket=t1)
        # Résolu en DEUX interventions → pas FTF.
        t2 = self._ticket(date_resolution=today)
        self._intervention(ticket=t2)
        self._intervention(ticket=t2)
        # Non résolu → exclu du calcul FTF.
        self._ticket()

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        ftf = resp.data['first_time_fix']
        self.assertEqual(ftf['nb_resolus'], 2)
        self.assertEqual(ftf['nb_ftf'], 1)
        self.assertEqual(ftf['pct_ftf'], 50.0)

    def test_mttr_average_days(self):
        today = date.today()
        t1 = self._ticket(date_resolution=today)
        Ticket.objects.filter(pk=t1.pk).update(
            date_creation=datetime.combine(today - timedelta(days=2), datetime.min.time()))
        t2 = self._ticket(date_resolution=today)
        Ticket.objects.filter(pk=t2.pk).update(
            date_creation=datetime.combine(today - timedelta(days=4), datetime.min.time()))

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['mttr_jours_moyen'], 3.0)

    def test_recidive_rate(self):
        self._ticket(est_recidive=True)
        self._ticket(est_recidive=False)
        self._ticket(est_recidive=False)

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        recidive = resp.data['recidive']
        self.assertEqual(recidive['total'], 1)
        self.assertAlmostEqual(recidive['taux_pct'], 33.3, places=1)

    def test_interventions_par_type_et_statut(self):
        self._intervention(
            type_intervention=Intervention.Type.POSE,
            statut=Intervention.Statut.TERMINEE)
        self._intervention(
            type_intervention=Intervention.Type.DEPANNAGE,
            statut=Intervention.Statut.PRETE)

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_interventions'], 2)
        types = {p['type']: p['total'] for p in resp.data['par_type']}
        self.assertEqual(types.get('pose'), 1)
        self.assertEqual(types.get('depannage'), 1)
        statuts = {p['statut']: p['total'] for p in resp.data['par_statut']}
        self.assertEqual(statuts.get('terminee'), 1)
        self.assertEqual(statuts.get('prete'), 1)

    def test_trajet_vs_sur_site(self):
        now = datetime.now()
        self._intervention(
            depart_depot_le=now - timedelta(minutes=90),
            arrivee_site_le=now - timedelta(minutes=60),
            retour_depot_le=now,
        )
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        temps = resp.data['temps_trajet_vs_site']
        self.assertEqual(temps['trajet_moyen_min'], 30)
        self.assertEqual(temps['duree_sur_site_moyenne_min'], 60)

    def test_filters_by_technicien(self):
        other_tech = User.objects.create_user(
            username='xfsm16_tech2', password='x', company=self.company)
        self._ticket(technicien_responsable=self.tech)
        self._ticket(technicien_responsable=other_tech)

        resp = self.api.get(URL, {'technicien': self.tech.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_tickets'], 1)

    def test_multi_tenant_scoping(self):
        other_co = Company.objects.create(slug='xfsm16-other', nom='Autre Co')
        other_client = Client.objects.create(company=other_co, nom='Autre client')
        Ticket.objects.create(
            company=other_co, reference='T-OTHER', client=other_client)

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_tickets'], 0)

    def test_export_xlsx(self):
        self._ticket()
        resp = self.api.get(URL, {'export': 'xlsx'})
        body = b''.join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b'PK'))

    def test_par_technicien_breakdown(self):
        today = date.today()
        t1 = self._ticket(date_resolution=today)
        self._intervention(ticket=t1)

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        entry = next(
            p for p in resp.data['par_technicien']
            if p['technicien_id'] == self.tech.id)
        self.assertEqual(entry['total_tickets'], 1)
        self.assertEqual(entry['pct_ftf'], 100.0)
