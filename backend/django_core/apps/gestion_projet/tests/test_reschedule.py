"""Tests du drag-reschedule des tâches (PROJ11).

Couvre : pose du nouveau créneau, propagation FS qui POUSSE un successeur,
conservation de la durée du successeur, propagation EN CASCADE (chaîne),
non-régression (un successeur déjà assez tard n'est pas tiré plus tôt), types
SS/FF + lag, date_fin déduite quand absente, garde date_fin < date_debut,
endpoint scopé société et accès Administrateur/Responsable.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import services
from apps.gestion_projet.models import DependanceTache, Projet, Tache

User = get_user_model()
FS = DependanceTache.TypeDependance.FS
SS = DependanceTache.TypeDependance.SS
FF = DependanceTache.TypeDependance.FF


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


class RescheduleServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-resch', 'S')
        self.p = Projet.objects.create(company=self.co, code='P', nom='P')

    def _t(self, lib, debut, fin):
        return Tache.objects.create(
            company=self.co, projet=self.p, libelle=lib,
            date_debut_prevue=debut, date_fin_prevue=fin)

    def _dep(self, pred, succ, type_dep=FS, lag=0):
        return DependanceTache.objects.create(
            company=self.co, predecesseur=pred, successeur=succ,
            type_dependance=type_dep, lag=lag)

    def test_fs_pushes_successor(self):
        a = self._t('A', date(2026, 1, 1), date(2026, 1, 5))   # 4 days
        b = self._t('B', date(2026, 1, 5), date(2026, 1, 8))   # 3 days
        self._dep(a, b)
        # Drag A to start later: 2026-01-10 .. 2026-01-14 (keep 4 days).
        modifies = services.reprogrammer_tache(
            a, date(2026, 1, 10), date(2026, 1, 14))
        b.refresh_from_db()
        # B must start at A.fin = 2026-01-14, keep duration 3.
        self.assertEqual(b.date_debut_prevue, date(2026, 1, 14))
        self.assertEqual(b.date_fin_prevue, date(2026, 1, 17))
        self.assertEqual([t.id for t in modifies], [a.id, b.id])

    def test_cascade(self):
        a = self._t('A', date(2026, 1, 1), date(2026, 1, 3))   # 2 days
        b = self._t('B', date(2026, 1, 3), date(2026, 1, 5))   # 2 days
        c = self._t('C', date(2026, 1, 5), date(2026, 1, 6))   # 1 day
        self._dep(a, b)
        self._dep(b, c)
        services.reprogrammer_tache(a, date(2026, 1, 11), date(2026, 1, 13))
        b.refresh_from_db()
        c.refresh_from_db()
        self.assertEqual(b.date_debut_prevue, date(2026, 1, 13))
        self.assertEqual(b.date_fin_prevue, date(2026, 1, 15))
        self.assertEqual(c.date_debut_prevue, date(2026, 1, 15))
        self.assertEqual(c.date_fin_prevue, date(2026, 1, 16))

    def test_no_pull_earlier(self):
        # B already starts well after A's new finish -> untouched.
        a = self._t('A', date(2026, 1, 1), date(2026, 1, 5))
        b = self._t('B', date(2026, 2, 1), date(2026, 2, 4))
        self._dep(a, b)
        modifies = services.reprogrammer_tache(
            a, date(2026, 1, 3), date(2026, 1, 7))
        b.refresh_from_db()
        # B unchanged (2026-02-01 >= A.fin 2026-01-07).
        self.assertEqual(b.date_debut_prevue, date(2026, 2, 1))
        self.assertEqual([t.id for t in modifies], [a.id])

    def test_ss_with_lag(self):
        a = self._t('A', date(2026, 1, 1), date(2026, 1, 5))
        b = self._t('B', date(2026, 1, 1), date(2026, 1, 3))   # 2 days
        self._dep(a, b, SS, lag=2)
        services.reprogrammer_tache(a, date(2026, 1, 10), date(2026, 1, 14))
        b.refresh_from_db()
        # SS: B start >= A.start(2026-01-10) + 2 = 2026-01-12, keep 2 days.
        self.assertEqual(b.date_debut_prevue, date(2026, 1, 12))
        self.assertEqual(b.date_fin_prevue, date(2026, 1, 14))

    def test_ff(self):
        a = self._t('A', date(2026, 1, 1), date(2026, 1, 5))
        b = self._t('B', date(2026, 1, 2), date(2026, 1, 4))   # 2 days
        self._dep(a, b, FF, lag=0)
        services.reprogrammer_tache(a, date(2026, 1, 10), date(2026, 1, 16))
        b.refresh_from_db()
        # FF: B finish >= A.finish 2026-01-16 -> start = 16 - 2 = 2026-01-14.
        self.assertEqual(b.date_fin_prevue, date(2026, 1, 16))
        self.assertEqual(b.date_debut_prevue, date(2026, 1, 14))

    def test_default_end_keeps_duration(self):
        a = self._t('A', date(2026, 1, 1), date(2026, 1, 5))   # 4 days
        modifies = services.reprogrammer_tache(a, date(2026, 1, 10))
        a.refresh_from_db()
        self.assertEqual(a.date_debut_prevue, date(2026, 1, 10))
        self.assertEqual(a.date_fin_prevue, date(2026, 1, 14))  # +4
        self.assertEqual(len(modifies), 1)

    def test_invalid_dates_raise(self):
        a = self._t('A', date(2026, 1, 1), date(2026, 1, 5))
        with self.assertRaises(services.RescheduleError):
            services.reprogrammer_tache(a, date(2026, 1, 10), date(2026, 1, 9))


class RescheduleEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('gp-resch-a', 'A')
        self.co_b = make_company('gp-resch-b', 'B')
        self.user_a = make_user(self.co_a, 'resch-a')
        self.p = Projet.objects.create(company=self.co_a, code='P', nom='P')
        self.a = Tache.objects.create(
            company=self.co_a, projet=self.p, libelle='A',
            date_debut_prevue=date(2026, 1, 1),
            date_fin_prevue=date(2026, 1, 5))
        self.b = Tache.objects.create(
            company=self.co_a, projet=self.p, libelle='B',
            date_debut_prevue=date(2026, 1, 5),
            date_fin_prevue=date(2026, 1, 8))
        DependanceTache.objects.create(
            company=self.co_a, predecesseur=self.a, successeur=self.b)
        self.url = (f'/api/django/gestion-projet/taches/{self.a.id}/'
                    f'reprogrammer/')

    def test_endpoint_reschedules(self):
        resp = auth(self.user_a).post(
            self.url, {'date_debut': '2026-01-10', 'date_fin': '2026-01-14'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.b.refresh_from_db()
        self.assertEqual(self.b.date_debut_prevue, date(2026, 1, 14))
        self.assertEqual(len(resp.data), 2)

    def test_endpoint_requires_date_debut(self):
        resp = auth(self.user_a).post(self.url, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_bad_date_format(self):
        resp = auth(self.user_a).post(
            self.url, {'date_debut': 'not-a-date'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_cross_company_404(self):
        user_b = make_user(self.co_b, 'resch-b')
        resp = auth(user_b).post(
            self.url, {'date_debut': '2026-01-10'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_role_normal_403(self):
        normal = make_user(self.co_a, 'resch-normal', role='normal')
        resp = auth(normal).post(
            self.url, {'date_debut': '2026-01-10'}, format='json')
        self.assertEqual(resp.status_code, 403)
