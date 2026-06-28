"""Tests FG245 — Éditeur de calepinage toiture (placement panneaux).

Couvre :
  - RoofLayout.compute_grid : pavage rectangulaire correct (retraits + gap)
  - orientation portrait vs paysage change le compte
  - surface utile <= 0 → 0 panneau (jamais d'erreur)
  - build_panels : positions cohérentes avec la grille
  - recompute : compte calculé depuis la géométrie ; respecte panels fournis
  - puissance_kwc déduit du compte × Wc unitaire
  - API : create force company depuis le devis, ignore company du corps
  - API : panel_count est lecture seule (recalculé serveur)
  - API : isolation société (un devis d'une autre société est refusé / invisible)
  - API : action recompute renvoie le calepinage à jour
  - RULE #4 : créer/maj un calepinage ne change jamais le statut du devis

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_fg245_roof_layout -v 2
"""
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import Devis, RoofLayout

User = get_user_model()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_company(slug='fg245'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': 'Test FG245'})
    return company


def make_user(company):
    username = f'fg245_{company.slug}'
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return User.objects.create_user(
            username=username, password='x',
            role_legacy='responsable', company=company)


def make_client_obj(company):
    return Client.objects.create(
        company=company, nom='Rachidi', prenom='Omar',
        email=f'o_{company.slug}@example.com', telephone='+212622000000')


def make_devis(company, user, client, ref='DEV-FG245-1'):
    return Devis.objects.create(
        company=company, reference=ref, client=client,
        statut='brouillon', created_by=user)


# ─── Calcul du calepinage (modèle) ───────────────────────────────────────────

class TestRoofLayoutCompute(TestCase):

    def setUp(self):
        self.company = make_company('fg245-calc')

    def _layout(self, **kw):
        defaults = dict(
            company=self.company,
            largeur_m=Decimal('10'), hauteur_m=Decimal('6'),
            retrait_m=Decimal('0'),
            module_largeur_m=Decimal('1'), module_hauteur_m=Decimal('2'),
            espacement_m=Decimal('0'),
            orientation='portrait',
        )
        defaults.update(kw)
        return RoofLayout(**defaults)

    def test_grid_simple_no_gap_no_retrait(self):
        # 10 wide / 1 = 10 cols ; 6 high / 2 = 3 rows → 30 modules
        layout = self._layout()
        grid = layout.compute_grid()
        self.assertEqual(grid['cols'], 10)
        self.assertEqual(grid['rows'], 3)
        self.assertEqual(grid['count'], 30)

    def test_retrait_reduces_usable_surface(self):
        # 0.5 m retrait on each edge → usable 9 x 5
        layout = self._layout(retrait_m=Decimal('0.5'))
        grid = layout.compute_grid()
        # 9 / 1 = 9 cols ; 5 / 2 = 2 rows → 18
        self.assertEqual(grid['cols'], 9)
        self.assertEqual(grid['rows'], 2)
        self.assertEqual(grid['count'], 18)

    def test_gap_between_modules(self):
        # gap 0.5 : cols = (10+0.5)//(1+0.5) = 10.5//1.5 = 7
        layout = self._layout(espacement_m=Decimal('0.5'))
        grid = layout.compute_grid()
        self.assertEqual(grid['cols'], 7)

    def test_orientation_paysage_swaps_dims(self):
        # paysage swaps module w/h: module becomes 2 wide x 1 high
        portrait = self._layout(orientation='portrait')
        paysage = self._layout(orientation='paysage')
        # portrait: 10 cols x 3 rows = 30 ; paysage: 5 cols x 6 rows = 30
        self.assertEqual(portrait.compute_grid()['count'], 30)
        pg = paysage.compute_grid()
        self.assertEqual(pg['cols'], 5)
        self.assertEqual(pg['rows'], 6)
        self.assertEqual(pg['count'], 30)

    def test_negative_usable_returns_zero(self):
        # retrait larger than half the pan → no usable surface
        layout = self._layout(retrait_m=Decimal('6'))
        self.assertEqual(layout.compute_grid()['count'], 0)

    def test_zero_module_dims_returns_zero(self):
        layout = self._layout(module_largeur_m=Decimal('0'))
        self.assertEqual(layout.compute_grid()['count'], 0)

    def test_build_panels_count_matches_grid(self):
        layout = self._layout()
        panels = layout.build_panels()
        self.assertEqual(len(panels), 30)
        # first panel at the retrait origin
        self.assertEqual(panels[0]['x'], 0.0)
        self.assertEqual(panels[0]['y'], 0.0)
        self.assertEqual(panels[0]['w'], 1.0)
        self.assertEqual(panels[0]['h'], 2.0)

    def test_build_panels_respects_retrait_origin(self):
        layout = self._layout(retrait_m=Decimal('0.5'))
        panels = layout.build_panels()
        self.assertEqual(panels[0]['x'], 0.5)
        self.assertEqual(panels[0]['y'], 0.5)

    def test_recompute_from_geometry(self):
        layout = self._layout()
        layout.recompute(rebuild_panels=True)
        self.assertEqual(layout.panel_count, 30)
        self.assertEqual(len(layout.panels), 30)

    def test_recompute_respects_manual_panels(self):
        # explicit placement (5 panels) → count is len(panels), not the grid
        layout = self._layout()
        layout.panels = [{'x': 0, 'y': 0, 'w': 1, 'h': 2} for _ in range(5)]
        layout.recompute(rebuild_panels=False)
        self.assertEqual(layout.panel_count, 5)

    def test_puissance_kwc(self):
        layout = self._layout(puissance_module_wc=550)
        layout.recompute(rebuild_panels=True)  # 30 panels
        # 30 * 550 / 1000 = 16.5
        self.assertEqual(layout.puissance_kwc, 16.5)

    def test_puissance_kwc_none_when_unknown(self):
        layout = self._layout(puissance_module_wc=0)
        layout.recompute(rebuild_panels=True)
        self.assertIsNone(layout.puissance_kwc)


# ─── API CRUD + multi-tenancy ────────────────────────────────────────────────

class TestRoofLayoutAPI(TestCase):

    def setUp(self):
        self.company = make_company('fg245-api')
        self.user = make_user(self.company)
        self.client_obj = make_client_obj(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _payload(self, **kw):
        data = dict(
            devis=self.devis.pk,
            nom='Pan sud',
            largeur_m='10', hauteur_m='6', retrait_m='0',
            module_largeur_m='1', module_hauteur_m='2', espacement_m='0',
            orientation='portrait', puissance_module_wc=550,
        )
        data.update(kw)
        return data

    def test_create_computes_panel_count_server_side(self):
        resp = self.api.post(
            '/api/django/ventes/calepinages/', self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['panel_count'], 30)
        self.assertEqual(len(resp.data['panels']), 30)

    def test_panel_count_is_read_only(self):
        # client tries to force a bogus count → server ignores it
        resp = self.api.post(
            '/api/django/ventes/calepinages/',
            self._payload(panel_count=9999), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['panel_count'], 30)

    def test_create_forces_company_from_devis(self):
        resp = self.api.post(
            '/api/django/ventes/calepinages/', self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        layout = RoofLayout.objects.get(pk=resp.data['id'])
        self.assertEqual(layout.company_id, self.company.id)
        self.assertEqual(layout.created_by_id, self.user.id)

    def test_create_never_changes_devis_statut(self):
        before = self.devis.statut
        self.api.post(
            '/api/django/ventes/calepinages/', self._payload(), format='json')
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, before)

    def test_update_recomputes_count(self):
        resp = self.api.post(
            '/api/django/ventes/calepinages/', self._payload(), format='json')
        lid = resp.data['id']
        # widen pan → more columns
        resp2 = self.api.patch(
            f'/api/django/ventes/calepinages/{lid}/',
            {'largeur_m': '20'}, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['panel_count'], 60)  # 20 cols x 3 rows

    def test_recompute_action(self):
        resp = self.api.post(
            '/api/django/ventes/calepinages/', self._payload(), format='json')
        lid = resp.data['id']
        resp2 = self.api.post(
            f'/api/django/ventes/calepinages/{lid}/recompute/', {}, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['panel_count'], 30)

    def test_filter_by_devis(self):
        self.api.post(
            '/api/django/ventes/calepinages/', self._payload(), format='json')
        resp = self.api.get(
            f'/api/django/ventes/calepinages/?devis={self.devis.pk}')
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(results), 1)


# ─── Isolation société ───────────────────────────────────────────────────────

class TestRoofLayoutIsolation(TestCase):

    def setUp(self):
        self.co1 = make_company('fg245-iso1')
        self.co2 = make_company('fg245-iso2')
        self.u1 = make_user(self.co1)
        self.u2 = make_user(self.co2)
        self.c1 = make_client_obj(self.co1)
        self.c2 = make_client_obj(self.co2)
        self.d2 = make_devis(self.co2, self.u2, self.c2, 'DEV-FG245-CO2')

    def test_cross_company_devis_refused(self):
        api = APIClient()
        api.force_authenticate(user=self.u1)
        resp = api.post('/api/django/ventes/calepinages/', {
            'devis': self.d2.pk, 'largeur_m': '10', 'hauteur_m': '6',
            'module_largeur_m': '1', 'module_hauteur_m': '2',
        }, format='json')
        # devis belongs to co2 → user from co1 cannot attach to it
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_list_is_company_scoped(self):
        # co2 creates a layout
        RoofLayout.objects.create(
            company=self.co2, devis=self.d2,
            largeur_m=Decimal('10'), hauteur_m=Decimal('6'),
            module_largeur_m=Decimal('1'), module_hauteur_m=Decimal('2'),
        )
        api = APIClient()
        api.force_authenticate(user=self.u1)
        resp = api.get('/api/django/ventes/calepinages/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(results), 0)  # co1 sees none of co2's
