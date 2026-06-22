"""Tests de l'API planning Gantt (PROJ10).

Couvre : barres en jours relatifs sans ``date_debut`` (dates None), barres
DATÉES quand le projet a une ``date_debut`` (projection calendaire), liste des
liens prédécesseur→successeur (type + lag), report du drapeau critique et des
marges du CPM, propagation du cycle, endpoint scopé société, accès
Administrateur/Responsable.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import DependanceTache, Projet, Tache

User = get_user_model()
FS = DependanceTache.TypeDependance.FS


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


class GanttTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-gantt', 'S')
        self.p = Projet.objects.create(company=self.co, code='P', nom='P')

    def _t(self, lib, charge):
        return Tache.objects.create(
            company=self.co, projet=self.p, libelle=lib,
            charge_estimee=Decimal(str(charge)))

    def _by_id(self, res):
        return {row['tache']: row for row in res['taches']}

    def test_relative_bars_without_date(self):
        a, b = self._t('A', 3), self._t('B', 2)
        DependanceTache.objects.create(
            company=self.co, predecesseur=a, successeur=b)
        res = selectors.planning_gantt(self.p)
        self.assertIsNone(res['date_origine'])
        rows = self._by_id(res)
        self.assertEqual((rows[a.id]['es'], rows[a.id]['ef']), (0, 3))
        self.assertIsNone(rows[a.id]['date_debut'])
        self.assertEqual(res['duree_projet'], 5)

    def test_dated_bars_with_date_debut(self):
        self.p.date_debut = date(2026, 1, 1)
        self.p.save(update_fields=['date_debut'])
        a, b = self._t('A', 3), self._t('B', 2)
        DependanceTache.objects.create(
            company=self.co, predecesseur=a, successeur=b)
        res = selectors.planning_gantt(self.p)
        self.assertEqual(res['date_origine'], '2026-01-01')
        rows = self._by_id(res)
        # A es=0 ef=3 -> debut 2026-01-01, fin 2026-01-03 (inclusive).
        self.assertEqual(rows[a.id]['date_debut'], '2026-01-01')
        self.assertEqual(rows[a.id]['date_fin'], '2026-01-03')
        # B es=3 ef=5 -> debut 2026-01-04, fin 2026-01-05.
        self.assertEqual(rows[b.id]['date_debut'], '2026-01-04')
        self.assertEqual(rows[b.id]['date_fin'], '2026-01-05')

    def test_links_listed(self):
        a, b = self._t('A', 3), self._t('B', 2)
        dep = DependanceTache.objects.create(
            company=self.co, predecesseur=a, successeur=b,
            type_dependance=FS, lag=1)
        res = selectors.planning_gantt(self.p)
        self.assertEqual(len(res['liens']), 1)
        lien = res['liens'][0]
        self.assertEqual(lien['source'], a.id)
        self.assertEqual(lien['cible'], b.id)
        self.assertEqual(lien['type'], FS)
        self.assertEqual(lien['lag'], 1)

    def test_critical_flag_and_status_carried(self):
        a = self._t('A', 5)
        a.statut = Tache.Statut.EN_COURS
        a.avancement_pct = 40
        a.save(update_fields=['statut', 'avancement_pct'])
        res = selectors.planning_gantt(self.p)
        rows = self._by_id(res)
        self.assertTrue(rows[a.id]['critique'])
        self.assertEqual(rows[a.id]['statut'], Tache.Statut.EN_COURS)
        self.assertEqual(rows[a.id]['avancement_pct'], 40)

    def test_cycle_propagates(self):
        a, b = self._t('A', 1), self._t('B', 1)
        DependanceTache.objects.create(
            company=self.co, predecesseur=a, successeur=b)
        DependanceTache.objects.create(
            company=self.co, predecesseur=b, successeur=a)
        res = selectors.planning_gantt(self.p)
        self.assertTrue(res['has_cycle'])
        self.assertEqual(res['taches'], [])
        self.assertEqual(len(res['liens']), 2)


class GanttEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('gp-gantt-a', 'A')
        self.co_b = make_company('gp-gantt-b', 'B')
        self.user_a = make_user(self.co_a, 'gantt-a')
        self.p = Projet.objects.create(
            company=self.co_a, code='P', nom='P', date_debut=date(2026, 2, 1))
        Tache.objects.create(
            company=self.co_a, projet=self.p, libelle='A',
            charge_estimee=Decimal('3'))
        self.url = f'/api/django/gestion-projet/projets/{self.p.id}/gantt/'

    def test_endpoint_returns_gantt(self):
        resp = auth(self.user_a).get(self.url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['date_origine'], '2026-02-01')
        self.assertEqual(len(resp.data['taches']), 1)

    def test_endpoint_cross_company_404(self):
        user_b = make_user(self.co_b, 'gantt-b')
        resp = auth(user_b).get(self.url)
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_role_normal_403(self):
        normal = make_user(self.co_a, 'gantt-normal', role='normal')
        resp = auth(normal).get(self.url)
        self.assertEqual(resp.status_code, 403)
