"""Tests du roll-up d'avancement pondéré par charge (PROJ9).

Couvre : roll-up d'une feuille (avancement propre), pondération par charge sur un
parent à plusieurs enfants, profondeur arbitraire (petits-enfants), repli en
moyenne ÉGALE quand la charge cumulée est nulle, avancement global du projet,
endpoint scopé société, accès Administrateur/Responsable.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import Projet, Tache

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RollupTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-roll', 'S')
        self.p = Projet.objects.create(company=self.co, code='P', nom='P')

    def _t(self, lib, charge=None, av=0, parent=None):
        return Tache.objects.create(
            company=self.co, projet=self.p, libelle=lib, parent=parent,
            avancement_pct=av,
            charge_estimee=None if charge is None else Decimal(str(charge)))

    def _by_id(self, nodes):
        out = {}

        def walk(ns):
            for n in ns:
                out[n['id']] = n
                walk(n['sous_taches'])
        walk(nodes)
        return out

    def test_leaf_keeps_own_avancement(self):
        self._t('A', charge=5, av=40)
        res = selectors.rollup_avancement(self.p)
        self.assertEqual(res['avancement_pct'], 40)

    def test_weighted_parent(self):
        # Parent with two leaves: charge 3 @ 100%, charge 1 @ 0%.
        # weighted = (100*3 + 0*1)/4 = 75.
        parent = self._t('P', charge=99)  # parent charge ignored (recomputed)
        self._t('C1', charge=3, av=100, parent=parent)
        self._t('C2', charge=1, av=0, parent=parent)
        res = selectors.rollup_avancement(self.p)
        rows = self._by_id(res['taches'])
        self.assertEqual(rows[parent.id]['avancement_pct'], 75)
        self.assertEqual(rows[parent.id]['charge'], 4.0)
        self.assertFalse(rows[parent.id]['est_feuille'])
        # Project-level equals parent (single root branch).
        self.assertEqual(res['avancement_pct'], 75)

    def test_depth_arbitrary(self):
        # root -> mid -> two leaves.
        root = self._t('R', charge=10)
        mid = self._t('M', charge=10, parent=root)
        self._t('L1', charge=2, av=50, parent=mid)
        self._t('L2', charge=2, av=100, parent=mid)
        res = selectors.rollup_avancement(self.p)
        rows = self._by_id(res['taches'])
        # mid = (50*2 + 100*2)/4 = 75 ; root rolls up to 75.
        self.assertEqual(rows[mid.id]['avancement_pct'], 75)
        self.assertEqual(rows[root.id]['avancement_pct'], 75)
        self.assertEqual(res['avancement_pct'], 75)

    def test_equal_weight_when_no_charge(self):
        # Two leaves with no charge: equal mean (40 + 80)/2 = 60.
        parent = self._t('P')
        self._t('C1', av=40, parent=parent)
        self._t('C2', av=80, parent=parent)
        res = selectors.rollup_avancement(self.p)
        rows = self._by_id(res['taches'])
        self.assertEqual(rows[parent.id]['avancement_pct'], 60)
        self.assertEqual(rows[parent.id]['charge'], 0.0)

    def test_project_weighted_across_roots(self):
        # Two root leaves: charge 4 @ 100, charge 1 @ 0 => 80.
        self._t('R1', charge=4, av=100)
        self._t('R2', charge=1, av=0)
        res = selectors.rollup_avancement(self.p)
        self.assertEqual(res['avancement_pct'], 80)
        self.assertEqual(res['charge_totale'], 5.0)

    def test_empty_project(self):
        res = selectors.rollup_avancement(self.p)
        self.assertEqual(res['avancement_pct'], 0)
        self.assertEqual(res['taches'], [])

    def test_rounding(self):
        # (100*1 + 0*2)/3 = 33.33 -> 33.
        parent = self._t('P')
        self._t('C1', charge=1, av=100, parent=parent)
        self._t('C2', charge=2, av=0, parent=parent)
        res = selectors.rollup_avancement(self.p)
        rows = self._by_id(res['taches'])
        self.assertEqual(rows[parent.id]['avancement_pct'], 33)


class RollupEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('gp-roll-a', 'A')
        self.co_b = make_company('gp-roll-b', 'B')
        self.user_a = make_user(self.co_a, 'roll-a')
        self.p = Projet.objects.create(company=self.co_a, code='P', nom='P')
        Tache.objects.create(
            company=self.co_a, projet=self.p, libelle='A',
            charge_estimee=Decimal('5'), avancement_pct=60)
        self.url = f'/api/django/gestion-projet/projets/{self.p.id}/avancement/'

    def test_endpoint_returns_rollup(self):
        resp = auth(self.user_a).get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['avancement_pct'], 60)

    def test_endpoint_cross_company_404(self):
        user_b = make_user(self.co_b, 'roll-b')
        resp = auth(user_b).get(self.url)
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_role_normal_403(self):
        normal = make_user(self.co_a, 'roll-normal', role='normal')
        resp = auth(normal).get(self.url)
        self.assertEqual(resp.status_code, 403)
