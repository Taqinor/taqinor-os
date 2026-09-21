"""Tests des alertes de dépassement budgétaire (PROJ23).

Couvre : aucune alerte quand le réel reste sous le seuil ; alerte de seuil
(consommation ≥ seuil_pct ≤ 100 %) ; dépassement (réel > budget) ; budget nul +
réel positif → dépassement non borné (consommation None) ; seuil personnalisé ;
seuil invalide ramené au défaut/borné ; scoping société (404 cross-tenant) ;
accès réservé au palier Administrateur/Responsable (rôle ``normal`` → 403).

Le réel de main-d'œuvre est 100 % INTERNE (affectations × coût horaire) ; les
catégories matériel/sous-traitance dégradent à 0 (frontière cross-app).
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
    RessourceProfil,
    Tache,
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


def _mo_reelle(co, projet, charge_jours, cout_horaire):
    """Pose une affectation MO réelle = charge × 8h × coût horaire."""
    tache = Tache.objects.create(
        company=co, projet=projet, libelle='T', ordre=1)
    ressource = RessourceProfil.objects.create(
        company=co, nom='R', cout_horaire=Decimal(cout_horaire))
    AffectationRessource.objects.create(
        company=co, tache=tache, ressource=ressource,
        date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 2),
        charge_jours=Decimal(charge_jours))


class AlertesBudgetSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-alb-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-ALB', nom='Projet alertes')

    def _budget(self, mo_prevu):
        budget = BudgetProjet.objects.create(
            company=self.co, projet=self.projet, version=1,
            statut=BudgetProjet.Statut.VALIDE)
        LigneBudgetProjet.objects.create(
            company=self.co, budget=budget,
            categorie=LigneBudgetProjet.Categorie.MAIN_OEUVRE,
            libelle='MO', montant_prevu=Decimal(mo_prevu))
        return budget

    def test_pas_alerte_sous_le_seuil(self):
        self._budget('10000')
        # réel MO = 1 j × 8h × 100 = 800 → 8 % du budget.
        _mo_reelle(self.co, self.projet, '1', '100')
        data = selectors.alertes_depassement_budgetaire(self.co, self.projet)
        self.assertFalse(data['en_depassement'])
        self.assertEqual(data['nb_alertes'], 0)
        self.assertEqual(data['total']['niveau'], 'ok')

    def test_alerte_seuil_atteint(self):
        self._budget('1000')
        # réel MO = 1 j × 8h × 120 = 960 → 96 % ≥ seuil 90.
        _mo_reelle(self.co, self.projet, '1', '120')
        data = selectors.alertes_depassement_budgetaire(self.co, self.projet)
        self.assertFalse(data['en_depassement'])
        self.assertEqual(data['nb_alertes'], 1)
        alerte = data['alertes'][0]
        self.assertEqual(
            alerte['categorie'], LigneBudgetProjet.Categorie.MAIN_OEUVRE)
        self.assertEqual(alerte['niveau'], 'alerte')

    def test_depassement(self):
        self._budget('500')
        # réel MO = 1 j × 8h × 100 = 800 > 500 → dépassement.
        _mo_reelle(self.co, self.projet, '1', '100')
        data = selectors.alertes_depassement_budgetaire(self.co, self.projet)
        self.assertTrue(data['en_depassement'])
        alerte = next(
            a for a in data['alertes']
            if a['categorie'] == LigneBudgetProjet.Categorie.MAIN_OEUVRE)
        self.assertEqual(alerte['niveau'], 'depassement')
        self.assertEqual(alerte['depassement'], Decimal('300.00'))

    def test_budget_nul_reel_positif_depassement_non_borne(self):
        # Aucun budget → réel MO positif = dépassement, consommation None.
        _mo_reelle(self.co, self.projet, '1', '100')
        data = selectors.alertes_depassement_budgetaire(self.co, self.projet)
        self.assertTrue(data['en_depassement'])
        alerte = next(
            a for a in data['alertes']
            if a['categorie'] == LigneBudgetProjet.Categorie.MAIN_OEUVRE)
        self.assertEqual(alerte['niveau'], 'depassement')
        self.assertIsNone(alerte['consommation_pct'])

    def test_seuil_personnalise(self):
        self._budget('1000')
        # réel = 800 → 80 % : pas d'alerte à 90, alerte à 70.
        _mo_reelle(self.co, self.projet, '1', '100')
        d90 = selectors.alertes_depassement_budgetaire(self.co, self.projet)
        self.assertEqual(d90['nb_alertes'], 0)
        d70 = selectors.alertes_depassement_budgetaire(
            self.co, self.projet, seuil_pct=70)
        self.assertEqual(d70['nb_alertes'], 1)


class AlertesBudgetApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-alb-a', 'A')
        self.co_b = make_company('gp-alb-b', 'B')
        self.user_a = make_user(self.co_a, 'alb-a')
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A')
        budget = BudgetProjet.objects.create(
            company=self.co_a, projet=self.projet, version=1,
            statut=BudgetProjet.Statut.VALIDE)
        LigneBudgetProjet.objects.create(
            company=self.co_a, budget=budget,
            categorie=LigneBudgetProjet.Categorie.MAIN_OEUVRE,
            libelle='MO', montant_prevu=Decimal('500'))
        _mo_reelle(self.co_a, self.projet, '1', '100')  # réel 800 > 500

    def test_alertes_budget_endpoint(self):
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{self.projet.id}/alertes-budget/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['en_depassement'])
        self.assertEqual(resp.data['total']['niveau'], 'depassement')
        self.assertEqual(resp.data['seuil_pct'], '90')

    def test_seuil_invalide_ramene_au_defaut(self):
        api = auth(self.user_a)
        resp = api.get(
            f'{self.BASE}{self.projet.id}/alertes-budget/?seuil_pct=zzz')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['seuil_pct'], '90')

    def test_cross_tenant_404(self):
        autre = Projet.objects.create(
            company=self.co_b, code='P-B', nom='B')
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{autre.id}/alertes-budget/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'alb-normal', role='normal')
        api = auth(normal)
        resp = api.get(f'{self.BASE}{self.projet.id}/alertes-budget/')
        self.assertEqual(resp.status_code, 403)
