"""N85 — vue carte : agrégation géographique (multi-tenant, lecture seule)."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.installations.models import Installation, Intervention
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/geo/'


class TestGeoPoints(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='geo-co', defaults={'nom': 'Geo Co'})[0]
        self.other = Company.objects.create(slug='geo-other', nom='Autre')
        self.user = User.objects.create_user(
            username='geo_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client A')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    # ── Helpers ───────────────────────────────────────────────────────────
    def _lead(self, company=None, **kw):
        return Lead.objects.create(
            company=company or self.company,
            nom=kw.pop('nom', 'Prospect'),
            gps_lat=kw.pop('gps_lat', Decimal('33.589886')),
            gps_lng=kw.pop('gps_lng', Decimal('-7.603869')),
            **kw)

    def _chantier(self, company=None, **kw):
        client = kw.pop('client', None) or self.client_obj
        return Installation.objects.create(
            company=company or self.company,
            reference=kw.pop('reference', 'CH-1'),
            client=client,
            gps_lat=kw.pop('gps_lat', Decimal('34.020882')),
            gps_lng=kw.pop('gps_lng', Decimal('-6.841650')),
            **kw)

    def _points_by_type(self, data, type_key):
        return [p for p in data['points'] if p['type'] == type_key]

    # ── Tests ─────────────────────────────────────────────────────────────
    def test_lead_point_returned_with_detail_path(self):
        lead = self._lead(nom='Alaoui')
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        leads = self._points_by_type(resp.data, 'lead')
        self.assertEqual(len(leads), 1)
        p = leads[0]
        self.assertEqual(p['id'], f'lead-{lead.id}')
        self.assertEqual(p['detail_path'], f'/crm/leads?lead={lead.id}')
        self.assertEqual(p['lat'], 33.589886)
        self.assertEqual(p['lng'], -7.603869)
        self.assertEqual(p['statut'], lead.stage)
        self.assertEqual(p['statut_label'], lead.get_stage_display())

    def test_company_scoping_excludes_other_company(self):
        self._lead(nom='Mine')
        other_client = Client.objects.create(company=self.other, nom='B')
        Lead.objects.create(
            company=self.other, nom='Theirs',
            gps_lat=Decimal('31.0'), gps_lng=Decimal('-8.0'))
        self._chantier(reference='CH-MINE')
        Installation.objects.create(
            company=self.other, reference='CH-THEIRS',
            client=other_client,
            gps_lat=Decimal('35.0'), gps_lng=Decimal('-5.0'))
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200)
        labels = {p['label'] for p in resp.data['points']}
        self.assertIn('Mine', labels)
        self.assertNotIn('Theirs', labels)
        self.assertIn('CH-MINE', labels)
        self.assertNotIn('CH-THEIRS', labels)

    def test_records_without_gps_are_skipped(self):
        Lead.objects.create(company=self.company, nom='NoGPS')
        resp = self.api.get(URL)
        self.assertEqual(self._points_by_type(resp.data, 'lead'), [])

    def test_installed_vs_chantier_classification(self):
        # Statut canonique amont → chantier ; canonique « installé » → installe.
        self._chantier(reference='CH-INPROG',
                       statut=Installation.Statut.PLANIFIE)
        self._chantier(reference='CH-DONE',
                       statut=Installation.Statut.RECEPTIONNE)
        resp = self.api.get(URL)
        chantiers = {p['label'] for p in self._points_by_type(
            resp.data, 'chantier')}
        installes = {p['label'] for p in self._points_by_type(
            resp.data, 'installe')}
        self.assertIn('CH-INPROG', chantiers)
        self.assertIn('CH-DONE', installes)
        self.assertNotIn('CH-DONE', chantiers)

    def test_legacy_statut_is_canonicalised_for_classification(self):
        # Statut HÉRITÉ « pose » → rabattu sur INSTALLE (canonique) → installe.
        self._chantier(reference='CH-LEGACY',
                       statut=Installation.Statut.POSE)
        resp = self.api.get(URL)
        installes = {p['label'] for p in self._points_by_type(
            resp.data, 'installe')}
        self.assertIn('CH-LEGACY', installes)

    def test_type_filter_restricts_output(self):
        self._lead(nom='OnlyLead')
        self._chantier(reference='CH-HIDDEN')
        resp = self.api.get(URL + '?types=lead')
        types = {p['type'] for p in resp.data['points']}
        self.assertEqual(types, {'lead'})

    def test_statut_filter_restricts_leads_by_stage(self):
        from apps.crm.stages import STAGES
        first, second = STAGES[0], STAGES[1]
        self._lead(nom='LeadFirst', stage=first)
        self._lead(nom='LeadSecond', stage=second,
                   gps_lat=Decimal('32.0'), gps_lng=Decimal('-6.0'))
        resp = self.api.get(URL + f'?types=lead&statuts={first}')
        labels = {p['label'] for p in self._points_by_type(resp.data, 'lead')}
        self.assertIn('LeadFirst', labels)
        self.assertNotIn('LeadSecond', labels)

    def test_visite_points_from_lead_chantier_and_intervention(self):
        soon = date.today() + timedelta(days=5)
        self._lead(nom='ToVisit', visite_prevue_le=soon,
                   visite_effectuee=False)
        ch = self._chantier(reference='CH-POSE', date_pose_prevue=soon)
        Intervention.objects.create(
            company=self.company, installation=ch,
            type_intervention=Intervention.Type.CONTROLE, date_prevue=soon)
        resp = self.api.get(URL + '?types=visite')
        visites = self._points_by_type(resp.data, 'visite')
        labels = {p['label'] for p in visites}
        self.assertTrue(any('Visite' in lbl for lbl in labels))
        self.assertTrue(any(lbl.startswith('Pose') for lbl in labels))
        # Toutes les visites portent une date et un detail_path.
        for p in visites:
            self.assertIn('date', p)
            self.assertTrue(p['detail_path'])

    def test_counts_total_matches_points(self):
        self._lead(nom='L1')
        self._chantier(reference='CH-C')
        resp = self.api.get(URL)
        self.assertEqual(resp.data['counts']['total'],
                         len(resp.data['points']))

    def test_requires_authentication(self):
        anon = APIClient()
        resp = anon.get(URL)
        self.assertIn(resp.status_code, (401, 403))
