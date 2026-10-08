"""ASEC41 — champs posés par le serveur du moteur publicitaire en lecture
seule ; ``parent`` d'une création borné à la société.

Constat C-ASEC-009 volet adsengine : un PATCH générique activait un plan de
vol (``status='actif'``) sans passer par le préflight, et réécrivait la
provenance d'une création (``depicts_real_client``, ``source_lane``,
``parent``) — dont le drapeau qui déclenche l'exigence de consentement.

Note : l'action ``plans-vol/validate/`` de la console NE MATÉRIALISE PAS un
plan (elle rend ``{ok, raisons}`` sans rien écrire) ; le seul chemin serveur
qui passe un plan en « actif » est ``flightplan.materialize`` (préflight
compris). ``test_validate_active`` vérifie ces deux faits.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.adsengine import flightplan
from apps.adsengine.models import CreativeAsset, FlightPlan
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/adsengine'


def _user(company, username):
    role = Role.objects.create(
        company=company, nom=username + '-role',
        permissions=['adsengine_view', 'adsengine_manage'])
    return User.objects.create_user(
        username=username, password='x', role=role, company=company)


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AdsChampsServeurTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='ASEC41 A', slug='asec41-a')
        self.b = Company.objects.create(nom='ASEC41 B', slug='asec41-b')
        self.manager = _user(self.a, 'asec41_manager')
        self.api = _api(self.manager)
        self.plan = FlightPlan.objects.create(company=self.a, name='Plan A')
        self.base_a = CreativeAsset.objects.create(
            company=self.a, asset_type='static')
        self.asset = CreativeAsset.objects.create(
            company=self.a, asset_type='static', source_lane='chantier',
            depicts_real_client=True, parent=self.base_a)
        self.asset_b = CreativeAsset.objects.create(
            company=self.b, asset_type='static')

    def test_flightplan_status_fige(self):
        r = self.api.patch(f'{BASE}/plans-vol/{self.plan.pk}/',
                           {'status': FlightPlan.Statut.ACTIF}, format='json')
        self.assertIn(r.status_code, (200, 400), r.content)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, FlightPlan.Statut.BROUILLON)
        r2 = self.api.post(f'{BASE}/plans-vol/', {
            'name': 'Plan né actif', 'status': FlightPlan.Statut.ACTIF},
            format='json')
        self.assertEqual(r2.status_code, 201, r2.content)
        self.assertEqual(FlightPlan.objects.get(pk=r2.data['id']).status,
                         FlightPlan.Statut.BROUILLON)

    def test_validate_active(self):
        # La console valide sans rien écrire…
        r = self.api.post(f'{BASE}/plans-vol/validate/',
                          {'phases': [{'key': 'hook'}], 'bras': [1, 2]},
                          format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('ok', r.data)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, FlightPlan.Statut.BROUILLON)
        # … et le chemin serveur d'activation garde ses contrôles : un plan
        # dont le préflight échoue (backlog vide) n'est PAS activé.
        with self.assertRaises(ValueError):
            flightplan.materialize(self.plan, flightplan.default_phase_specs())
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.status, FlightPlan.Statut.BROUILLON)

    def test_creative_champs_figes(self):
        r = self.api.patch(f'{BASE}/creatifs/{self.asset.pk}/', {
            'depicts_real_client': False, 'source_lane': 'autre',
            'parent': None}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.asset.refresh_from_db()
        self.assertTrue(self.asset.depicts_real_client)
        self.assertEqual(self.asset.source_lane, 'chantier')
        self.assertEqual(self.asset.parent_id, self.base_a.pk)

    def test_parent_etranger_400(self):
        r = self.api.patch(f'{BASE}/creatifs/{self.asset.pk}/',
                           {'parent': self.asset_b.pk}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('parent', r.data)
        r2 = self.api.post(f'{BASE}/creatifs/', {
            'asset_type': 'static', 'parent': self.asset_b.pk},
            format='json')
        self.assertEqual(r2.status_code, 400, r2.content)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.parent_id, self.base_a.pk)
