"""Tests FG148 — Campagnes de versement des commissions (payout run).

Couvre : la création d'un run avec lignes (total recalculé), le cycle de statut
brouillon -> validé -> posté, l'écriture OD au grand livre (6171 / 4432,
équilibrée), les refus de transition hors séquence, l'idempotence du poste, la
pose ``company`` / ``reference`` côté serveur, l'isolation multi-société et le
gate de rôle.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import CommissionPayoutRun, LigneEcriture

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


class CommissionRunServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('fg148-svc', 'FG148 Svc')
        self.user = make_user(self.co, 'fg148-svc-user')

    def _run(self):
        return services.creer_commission_run(
            self.co, date_run=date(2026, 3, 31), periode='2026-03',
            lignes=[
                {'commercial_nom': 'Sami', 'base': '100000', 'taux': '3',
                 'montant': '3000'},
                {'commercial_nom': 'Meriem', 'base': '50000', 'taux': '4',
                 'montant': '2000'},
            ],
            user=self.user)

    def test_creation_total_recalcule(self):
        run = self._run()
        self.assertTrue(run.reference.startswith('COMM-'))
        self.assertEqual(run.total, Decimal('5000'))
        self.assertEqual(run.lignes.count(), 2)
        self.assertEqual(run.statut, CommissionPayoutRun.Statut.BROUILLON)

    def test_cycle_valider_poster(self):
        run = self._run()
        services.valider_commission_run(run)
        run.refresh_from_db()
        self.assertEqual(run.statut, CommissionPayoutRun.Statut.VALIDE)
        services.poster_commission_run(run, user=self.user)
        run.refresh_from_db()
        self.assertEqual(run.statut, CommissionPayoutRun.Statut.POSTE)
        self.assertIsNotNone(run.ecriture_id)
        lignes = LigneEcriture.objects.filter(ecriture_id=run.ecriture_id)
        debit = sum((x.debit for x in lignes), Decimal('0'))
        credit = sum((x.credit for x in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertEqual(debit, Decimal('5000'))
        numeros = {x.compte.numero for x in lignes}
        self.assertIn('6171', numeros)
        self.assertIn('4432', numeros)

    def test_poster_sans_valider_refuse(self):
        run = self._run()
        with self.assertRaises(ValidationError):
            services.poster_commission_run(run, user=self.user)

    def test_poster_idempotent(self):
        run = self._run()
        services.valider_commission_run(run)
        services.poster_commission_run(run, user=self.user)
        ec1 = run.ecriture_id
        services.poster_commission_run(run, user=self.user)
        run.refresh_from_db()
        self.assertEqual(run.ecriture_id, ec1)


class CommissionRunApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg148-a', 'FG148 A')
        self.co_b = make_company('fg148-b', 'FG148 B')
        self.user_a = make_user(self.co_a, 'fg148-user-a')
        self.user_b = make_user(self.co_b, 'fg148-user-b')

    def test_create_avec_lignes(self):
        resp = auth(self.user_a).post(
            '/api/django/compta/commission-payout-runs/',
            {'date_run': '2026-03-31', 'periode': '2026-03',
             'company': self.co_b.id,
             'lignes': [
                 {'commercial_nom': 'Sami', 'montant': '1500'},
             ]},
            format='json')
        self.assertEqual(resp.status_code, 201)
        run = CommissionPayoutRun.objects.get(id=resp.data['id'])
        self.assertEqual(run.company_id, self.co_a.id)
        self.assertEqual(run.total, Decimal('1500'))

    def test_actions_valider_poster(self):
        run = services.creer_commission_run(
            self.co_a, date_run=date(2026, 3, 31),
            lignes=[{'commercial_nom': 'X', 'montant': '100'}],
            user=self.user_a)
        r1 = auth(self.user_a).post(
            f'/api/django/compta/commission-payout-runs/{run.id}/valider/',
            {}, format='json')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data['statut'], CommissionPayoutRun.Statut.VALIDE)
        r2 = auth(self.user_a).post(
            f'/api/django/compta/commission-payout-runs/{run.id}/poster/',
            {}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data['statut'], CommissionPayoutRun.Statut.POSTE)

    def test_isolation_liste(self):
        services.creer_commission_run(
            self.co_a, date_run=date(2026, 3, 31),
            lignes=[{'commercial_nom': 'X', 'montant': '100'}],
            user=self.user_a)
        resp_b = auth(self.user_b).get(
            '/api/django/compta/commission-payout-runs/')
        results = resp_b.data.get('results', resp_b.data)
        self.assertEqual(len(results), 0)

    def test_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg148-normal', role='normal')
        resp = auth(normal).post(
            '/api/django/compta/commission-payout-runs/',
            {'date_run': '2026-03-31'}, format='json')
        self.assertEqual(resp.status_code, 403)
