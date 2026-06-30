"""Tests du P&L de projet consolidé (PROJ26 — interne/admin).

Consolide : revenu (devis/factures rattachés, dégradé cross-app à 0 + note),
coûts (budget prévisionnel PROJ21 + réel affectations PROJ22 + timesheets
PROJ24), marges prév./réelle et marge % réelle (None si revenu nul).

Donnée 100 % INTERNE — jamais exposée au client. Couvre : agrégation des coûts
réels (affectations + timesheets) ; marge % None si revenu nul ; note revenu
quand des liens existent ; endpoint ; scoping (404 cross-tenant) ; accès
Administrateur/Responsable (403 pour ``normal``).
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
    AffectationRessource,
    BudgetProjet,
    LigneBudgetProjet,
    Projet,
    ProjetLien,
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


class PnlSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-pnl-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-PNL', nom='Projet P&L')
        budget = BudgetProjet.objects.create(
            company=self.co, projet=self.projet, version=1,
            statut=BudgetProjet.Statut.VALIDE)
        LigneBudgetProjet.objects.create(
            company=self.co, budget=budget,
            categorie=LigneBudgetProjet.Categorie.MAIN_OEUVRE,
            libelle='MO', montant_prevu=Decimal('5000'))

    def test_cout_reel_additionne_affectations_et_timesheets(self):
        tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        ressource = RessourceProfil.objects.create(
            company=self.co, nom='R', cout_horaire=Decimal('100'))
        # Affectation : 1 j × 8h × 100 = 800.
        AffectationRessource.objects.create(
            company=self.co, tache=tache, ressource=ressource,
            date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 2),
            charge_jours=Decimal('1'))
        # Timesheet : coût figé 300.
        Timesheet.objects.create(
            company=self.co, projet=self.projet, ressource=ressource,
            date=date(2026, 1, 1), heures=Decimal('3'), cout=Decimal('300'))
        data = selectors.pnl_projet(self.co, self.projet)
        self.assertEqual(data['cout_reel_affectations'], Decimal('800.00'))
        self.assertEqual(data['cout_reel_timesheets'], Decimal('300'))
        self.assertEqual(data['cout_reel'], Decimal('1100.00'))
        self.assertEqual(data['cout_budget'], Decimal('5000'))

    def test_marge_pct_none_si_revenu_nul(self):
        data = selectors.pnl_projet(self.co, self.projet)
        self.assertEqual(data['revenu'], Decimal('0'))
        self.assertIsNone(data['marge_pct_reelle'])

    def test_note_revenu_avec_liens(self):
        ProjetLien.objects.create(
            company=self.co, projet=self.projet,
            type_cible=ProjetLien.TypeCible.FACTURE, cible_id=7)
        data = selectors.pnl_projet(self.co, self.projet)
        self.assertIn('facture', data['note_revenu'])
        self.assertEqual(data['revenu'], Decimal('0'))


class PnlApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-pnl-a', 'A')
        self.co_b = make_company('gp-pnl-b', 'B')
        self.user_a = make_user(self.co_a, 'pnl-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A')

    def test_endpoint(self):
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{self.projet.id}/pnl/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['revenu'], '0')
        self.assertIsNone(resp.data['marge_pct_reelle'])

    def test_cross_tenant_404(self):
        autre = Projet.objects.create(company=self.co_b, code='P-B', nom='B')
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{autre.id}/pnl/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'pnl-normal', role='normal')
        api = auth(normal)
        resp = api.get(f'{self.BASE}{self.projet.id}/pnl/')
        self.assertEqual(resp.status_code, 403)
