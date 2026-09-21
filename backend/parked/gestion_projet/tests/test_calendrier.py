"""Tests du calendrier projet — jours ouvrés/fériés (PROJ12).

Couvre : calendrier par défaut (L–V) sans config, drapeaux de jours ouvrés
personnalisés, exclusion des jours fériés, comptage de jours ouvrés sur un
intervalle, ajout de N jours ouvrés (saut des week-ends/fériés), société posée
côté serveur, isolation multi-société, OneToOne (un calendrier par projet),
filtres et accès Administrateur/Responsable.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    CalendrierProjet,
    JourFerie,
    Projet,
)

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class CalendrierSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-cal', 'S')
        self.p = Projet.objects.create(company=self.co, code='P', nom='P')

    def test_default_mon_fri_when_no_calendar(self):
        # 2026-01-05 is a Monday ; 2026-01-10 Saturday, 11 Sunday.
        self.assertTrue(selectors.est_jour_ouvre(self.p, date(2026, 1, 5)))
        self.assertFalse(selectors.est_jour_ouvre(self.p, date(2026, 1, 10)))
        self.assertFalse(selectors.est_jour_ouvre(self.p, date(2026, 1, 11)))

    def test_count_working_days_default(self):
        # Mon 2026-01-05 .. Mon 2026-01-12 (exclusive) = 5 working days.
        n = selectors.jours_ouvres_entre(
            self.p, date(2026, 1, 5), date(2026, 1, 12))
        self.assertEqual(n, 5)

    def test_custom_working_flags(self):
        CalendrierProjet.objects.create(
            company=self.co, projet=self.p, samedi=True, dimanche=True)
        # Now Saturday is worked.
        self.assertTrue(selectors.est_jour_ouvre(self.p, date(2026, 1, 10)))

    def test_holiday_excluded(self):
        cal = CalendrierProjet.objects.create(
            company=self.co, projet=self.p)
        JourFerie.objects.create(
            company=self.co, calendrier=cal, date=date(2026, 1, 6),
            libelle='Férié test')
        # Tuesday 2026-01-06 now non-working.
        self.assertFalse(selectors.est_jour_ouvre(self.p, date(2026, 1, 6)))
        # Count Mon..Wed (exclusive Thu) with Tue holiday = Mon + Wed = 2.
        n = selectors.jours_ouvres_entre(
            self.p, date(2026, 1, 5), date(2026, 1, 8))
        self.assertEqual(n, 2)

    def test_add_working_days_skips_weekend(self):
        # Add 3 working days to Friday 2026-01-09 -> Wed 2026-01-14.
        # Fri+1=Mon(12), +2=Tue(13), +3=Wed(14).
        result = selectors.ajouter_jours_ouvres(
            self.p, date(2026, 1, 9), 3)
        self.assertEqual(result, date(2026, 1, 14))

    def test_add_working_days_skips_holiday(self):
        cal = CalendrierProjet.objects.create(
            company=self.co, projet=self.p)
        JourFerie.objects.create(
            company=self.co, calendrier=cal, date=date(2026, 1, 13))
        # Add 2 working days to Fri 2026-01-09: Mon(12), skip Tue(13)=holiday,
        # Wed(14) -> 2 days = 2026-01-14.
        result = selectors.ajouter_jours_ouvres(
            self.p, date(2026, 1, 9), 2)
        self.assertEqual(result, date(2026, 1, 14))


class CalendrierApiTests(TestCase):
    CAL = '/api/django/gestion-projet/calendriers/'
    FERIE = '/api/django/gestion-projet/jours-feries/'

    def setUp(self):
        self.co_a = make_company('gp-cal-a', 'A')
        self.co_b = make_company('gp-cal-b', 'B')
        self.user_a = make_user(self.co_a, 'cal-a')
        self.user_b = make_user(self.co_b, 'cal-b')
        self.p_a = Projet.objects.create(company=self.co_a, code='P', nom='P')

    def test_create_forces_company(self):
        resp = auth(self.user_a).post(
            self.CAL, {'projet': self.p_a.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cal = CalendrierProjet.objects.get(id=resp.data['id'])
        self.assertEqual(cal.company, self.co_a)

    def test_cross_company_projet_rejected(self):
        resp = auth(self.user_b).post(
            self.CAL, {'projet': self.p_a.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_holiday_and_nested(self):
        cal = CalendrierProjet.objects.create(
            company=self.co_a, projet=self.p_a)
        resp = auth(self.user_a).post(
            self.FERIE,
            {'calendrier': cal.id, 'date': '2026-01-06', 'libelle': 'Fête'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ferie = JourFerie.objects.get(id=resp.data['id'])
        self.assertEqual(ferie.company, self.co_a)
        # Nested read on calendar.
        resp_cal = auth(self.user_a).get(f'{self.CAL}{cal.id}/')
        self.assertEqual(len(resp_cal.data['jours_feries']), 1)

    def test_filter_holidays_by_projet(self):
        cal = CalendrierProjet.objects.create(
            company=self.co_a, projet=self.p_a)
        JourFerie.objects.create(
            company=self.co_a, calendrier=cal, date=date(2026, 1, 6))
        resp = auth(self.user_a).get(f'{self.FERIE}?projet={self.p_a.id}')
        self.assertEqual(len(rows(resp)), 1)

    def test_isolation(self):
        CalendrierProjet.objects.create(company=self.co_a, projet=self.p_a)
        resp = auth(self.user_b).get(self.CAL)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_403(self):
        normal = make_user(self.co_a, 'cal-normal', role='normal')
        resp = auth(normal).get(self.CAL)
        self.assertEqual(resp.status_code, 403)
