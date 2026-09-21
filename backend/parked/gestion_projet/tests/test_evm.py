"""Tests de l'EVM léger — valeur acquise (PROJ29).

Indicateurs : BAC / EV / AC / PV + CV / SV / CPI / SPI (donnée INTERNE). PV =
fraction de calendrier écoulée × BAC ; divisions gardées (dénominateur nul →
None). Couvre : EV depuis l'avancement physique ; AC = réel consolidé ; PV None
sans dates de projet ; PV/SPI calculés avec dates + date de référence ; CPI ;
endpoint ; scoping (404 cross-tenant) ; accès Administrateur/Responsable (403).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    Projet,
    RessourceProfil,
    Tache,
    Timesheet,
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


class EvmSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-evm-sel', 'S')

    def test_ev_ac_cpi(self):
        projet = Projet.objects.create(
            company=self.co, code='P-EVM', nom='P',
            budget_total=Decimal('100000'))
        # Avancement 50 % (tâche feuille charge 10).
        Tache.objects.create(
            company=self.co, projet=projet, libelle='T',
            avancement_pct=50, charge_estimee=Decimal('10'), ordre=1)
        # AC : timesheet figé 30000.
        res = RessourceProfil.objects.create(
            company=self.co, nom='R', cout_horaire=Decimal('100'))
        Timesheet.objects.create(
            company=self.co, projet=projet, ressource=res,
            date=date(2026, 1, 1), heures=Decimal('1'), cout=Decimal('30000'))
        data = selectors.evm_projet(self.co, projet)
        # EV = 50 % × 100000 = 50000.
        self.assertEqual(data['ev'], Decimal('50000.00'))
        # AC = 30000 (réel affectations 0 + timesheets 30000).
        self.assertEqual(data['ac'], Decimal('30000'))
        # CV = EV - AC = 20000.
        self.assertEqual(data['cv'], Decimal('20000.00'))
        # CPI = EV / AC = 50000/30000 = 1.6667.
        self.assertEqual(data['cpi'], Decimal('1.6667'))

    def test_pv_none_sans_dates(self):
        projet = Projet.objects.create(
            company=self.co, code='P-EVM2', nom='P',
            budget_total=Decimal('100000'))
        data = selectors.evm_projet(self.co, projet)
        self.assertIsNone(data['pv'])
        self.assertIsNone(data['sv'])
        self.assertIsNone(data['spi'])

    def test_pv_calcule_avec_dates(self):
        projet = Projet.objects.create(
            company=self.co, code='P-EVM3', nom='P',
            budget_total=Decimal('100000'),
            date_debut=date(2026, 1, 1), date_fin_prevue=date(2026, 1, 11))
        # Référence au milieu : 5 jours / 10 → 50 % écoulé → PV = 50000.
        data = selectors.evm_projet(
            self.co, projet, date_reference=date(2026, 1, 6))
        self.assertEqual(data['fraction_ecoulee_pct'], Decimal('50.00'))
        self.assertEqual(data['pv'], Decimal('50000.00'))


class EvmApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-evm-a', 'A')
        self.co_b = make_company('gp-evm-b', 'B')
        self.user_a = make_user(self.co_a, 'evm-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A',
            budget_total=Decimal('50000'))

    def test_endpoint(self):
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{self.projet.id}/evm/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['bac'], '50000.00')
        self.assertIn('cpi', resp.data)

    def test_cross_tenant_404(self):
        autre = Projet.objects.create(company=self.co_b, code='P-B', nom='B')
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{autre.id}/evm/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'evm-normal', role='normal')
        api = auth(normal)
        resp = api.get(f'{self.BASE}{self.projet.id}/evm/')
        self.assertEqual(resp.status_code, 403)
