"""Tests du chemin critique (PROJ8 — CPM + marges).

Couvre la dérivation de durée (dates/charge/défaut), le forward/backward pass
sur les quatre types de dépendance (FS/SS/FF/SF) et le lag, le calcul des marges
totale et libre, l'identification du chemin critique, l'exclusion des tâches
conteneurs (non-feuilles), la détection de cycle, l'endpoint scopé société et
l'accès réservé Administrateur/Responsable.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import cpm
from apps.gestion_projet.models import DependanceTache, Projet, Tache

User = get_user_model()
FS = DependanceTache.TypeDependance.FS
SS = DependanceTache.TypeDependance.SS
FF = DependanceTache.TypeDependance.FF
SF = DependanceTache.TypeDependance.SF


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


class DureeJoursTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-cpm-d', 'S')
        self.p = Projet.objects.create(company=self.co, code='P', nom='P')

    def _t(self, **kw):
        return Tache.objects.create(
            company=self.co, projet=self.p, libelle='T', **kw)

    def test_duree_from_charge_rounds_up(self):
        t = self._t(charge_estimee=Decimal('2.3'))
        self.assertEqual(cpm.duree_jours(t), 3)

    def test_duree_default_one(self):
        t = self._t()
        self.assertEqual(cpm.duree_jours(t), 1)

    def test_duree_from_dates(self):
        from datetime import date
        t = self._t(date_debut_prevue=date(2026, 1, 1),
                    date_fin_prevue=date(2026, 1, 6))
        self.assertEqual(cpm.duree_jours(t), 5)

    def test_duree_zero_charge_min_one(self):
        t = self._t(charge_estimee=Decimal('0'))
        self.assertEqual(cpm.duree_jours(t), 1)


class CpmMathTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-cpm-m', 'S')
        self.p = Projet.objects.create(company=self.co, code='P', nom='P')

    def _t(self, lib, charge):
        return Tache.objects.create(
            company=self.co, projet=self.p, libelle=lib,
            charge_estimee=Decimal(str(charge)))

    def _dep(self, pred, succ, type_dep=FS, lag=0):
        return DependanceTache.objects.create(
            company=self.co, predecesseur=pred, successeur=succ,
            type_dependance=type_dep, lag=lag)

    def _by_id(self, result):
        return {row['tache']: row for row in result['taches']}

    def test_empty_project(self):
        res = cpm.calculer_cpm(self.p)
        self.assertEqual(res['duree_projet'], 0)
        self.assertFalse(res['has_cycle'])
        self.assertEqual(res['taches'], [])

    def test_simple_fs_chain(self):
        # A(3) -> B(2) -> C(4) : durée projet = 9, tout critique.
        a, b, c = self._t('A', 3), self._t('B', 2), self._t('C', 4)
        self._dep(a, b)
        self._dep(b, c)
        res = cpm.calculer_cpm(self.p)
        self.assertEqual(res['duree_projet'], 9)
        rows = self._by_id(res)
        self.assertEqual((rows[a.id]['es'], rows[a.id]['ef']), (0, 3))
        self.assertEqual((rows[b.id]['es'], rows[b.id]['ef']), (3, 5))
        self.assertEqual((rows[c.id]['es'], rows[c.id]['ef']), (5, 9))
        for rid in (a.id, b.id, c.id):
            self.assertEqual(rows[rid]['marge_totale'], 0)
            self.assertTrue(rows[rid]['critique'])
        self.assertEqual(set(res['chemin_critique']), {a.id, b.id, c.id})

    def test_parallel_paths_slack(self):
        # A(2) -> C(4) ; A(2) -> B(1) -> C(4). Long path = A,B?,
        # Path1: A->C = 2+4=6 ; Path2: A->B->C = 2+1+... but C depends on both.
        a = self._t('A', 2)
        b = self._t('B', 1)
        c = self._t('C', 4)
        self._dep(a, b)
        self._dep(b, c)
        self._dep(a, c)
        res = cpm.calculer_cpm(self.p)
        rows = self._by_id(res)
        # A(0-2). B(2-3). C starts at max(EF(B)=3, EF(A)=2)=3, ends 7.
        self.assertEqual(res['duree_projet'], 7)
        self.assertEqual((rows[c.id]['es'], rows[c.id]['ef']), (3, 7))
        # Critical path A->B->C ; A->C direct edge has slack 1.
        self.assertEqual(rows[a.id]['marge_totale'], 0)
        self.assertEqual(rows[b.id]['marge_totale'], 0)
        self.assertEqual(rows[c.id]['marge_totale'], 0)
        # B free margin 0 (drives C). A drives B with no slack on that path.
        self.assertTrue(rows[a.id]['critique'])

    def test_lag_positive_pushes_successor(self):
        a, b = self._t('A', 3), self._t('B', 2)
        self._dep(a, b, FS, lag=2)
        res = cpm.calculer_cpm(self.p)
        rows = self._by_id(res)
        # B start = EF(A)=3 + lag 2 = 5, end 7.
        self.assertEqual((rows[b.id]['es'], rows[b.id]['ef']), (5, 7))
        self.assertEqual(res['duree_projet'], 7)

    def test_lag_negative_overlap(self):
        a, b = self._t('A', 5), self._t('B', 3)
        self._dep(a, b, FS, lag=-2)
        res = cpm.calculer_cpm(self.p)
        rows = self._by_id(res)
        # B start = EF(A)=5 - 2 = 3, end 6.
        self.assertEqual((rows[b.id]['es'], rows[b.id]['ef']), (3, 6))
        self.assertEqual(res['duree_projet'], 6)

    def test_ss_dependency(self):
        a, b = self._t('A', 4), self._t('B', 2)
        self._dep(a, b, SS, lag=1)
        res = cpm.calculer_cpm(self.p)
        rows = self._by_id(res)
        # B start = ES(A)=0 + 1 = 1, end 3. Project = max(EF(A)=4, 3)=4.
        self.assertEqual((rows[b.id]['es'], rows[b.id]['ef']), (1, 3))
        self.assertEqual(res['duree_projet'], 4)

    def test_ff_dependency(self):
        a, b = self._t('A', 5), self._t('B', 2)
        self._dep(a, b, FF, lag=0)
        res = cpm.calculer_cpm(self.p)
        rows = self._by_id(res)
        # B finish >= EF(A)=5 -> start = 5 - 2 = 3, end 5.
        self.assertEqual((rows[b.id]['es'], rows[b.id]['ef']), (3, 5))
        self.assertEqual(res['duree_projet'], 5)

    def test_sf_dependency(self):
        a, b = self._t('A', 4), self._t('B', 2)
        self._dep(a, b, SF, lag=3)
        res = cpm.calculer_cpm(self.p)
        rows = self._by_id(res)
        # B finish >= ES(A)=0 + 3 = 3 -> start = 3 - 2 = 1, end 3.
        self.assertEqual((rows[b.id]['es'], rows[b.id]['ef']), (1, 3))

    def test_free_margin_parallel(self):
        # A(2)->C ; B(5)->C. B is critical, A has free margin 3.
        a = self._t('A', 2)
        b = self._t('B', 5)
        c = self._t('C', 1)
        self._dep(a, c)
        self._dep(b, c)
        res = cpm.calculer_cpm(self.p)
        rows = self._by_id(res)
        # C es = max(2,5)=5. A ef=2, free margin to C(es 5) = 5-2 = 3.
        self.assertEqual(rows[a.id]['marge_libre'], 3)
        self.assertEqual(rows[a.id]['marge_totale'], 3)
        self.assertFalse(rows[a.id]['critique'])
        self.assertTrue(rows[b.id]['critique'])
        self.assertEqual(rows[b.id]['marge_libre'], 0)

    def test_container_tasks_excluded(self):
        # Parent container P with leaf child L ; only leaf in network.
        parent = self._t('P', 10)
        child = Tache.objects.create(
            company=self.co, projet=self.p, libelle='L',
            parent=parent, charge_estimee=Decimal('3'))
        res = cpm.calculer_cpm(self.p)
        ids = {row['tache'] for row in res['taches']}
        self.assertIn(child.id, ids)
        self.assertNotIn(parent.id, ids)

    def test_cycle_detection(self):
        # Build a 3-cycle A->B->C->A directly in DB bypassing clean guards.
        a, b, c = self._t('A', 1), self._t('B', 1), self._t('C', 1)
        self._dep(a, b)
        self._dep(b, c)
        DependanceTache.objects.create(
            company=self.co, predecesseur=c, successeur=a)
        res = cpm.calculer_cpm(self.p)
        self.assertTrue(res['has_cycle'])
        self.assertEqual(res['chemin_critique'], [])


class CpmEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('gp-cpm-a', 'A')
        self.co_b = make_company('gp-cpm-b', 'B')
        self.user_a = make_user(self.co_a, 'cpm-a')
        self.p = Projet.objects.create(company=self.co_a, code='P', nom='P')
        a = Tache.objects.create(
            company=self.co_a, projet=self.p, libelle='A',
            charge_estimee=Decimal('3'))
        b = Tache.objects.create(
            company=self.co_a, projet=self.p, libelle='B',
            charge_estimee=Decimal('2'))
        DependanceTache.objects.create(
            company=self.co_a, predecesseur=a, successeur=b)
        self.url = f'/api/django/gestion-projet/projets/{self.p.id}/chemin-critique/'

    def test_endpoint_returns_cpm(self):
        resp = auth(self.user_a).get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['duree_projet'], 5)
        self.assertEqual(len(resp.data['taches']), 2)

    def test_endpoint_cross_company_404(self):
        user_b = make_user(self.co_b, 'cpm-b')
        resp = auth(user_b).get(self.url)
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_role_normal_403(self):
        normal = make_user(self.co_a, 'cpm-normal', role='normal')
        resp = auth(normal).get(self.url)
        self.assertEqual(resp.status_code, 403)
