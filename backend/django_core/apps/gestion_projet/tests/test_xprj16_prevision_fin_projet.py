"""Tests XPRJ16 — prévision fin de projet (ETC/EAC).

Couvre : EAC/ETC corrects sur cas CPI <1/=1/>1/absent, endpoint scopé société,
et le fait qu'aucun montant interne n'apparaît dans le portail client
(``portail_avancement_client`` reste inchangé).
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


class PrevisionFinProjetTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj16', 'S')
        self.user = make_user(self.co, 'resp-xprj16')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X16', nom='Projet X16',
            budget_total=Decimal('10000'))
        budget = BudgetProjet.objects.create(
            company=self.co, projet=self.projet, version=1,
            statut=BudgetProjet.Statut.VALIDE)
        LigneBudgetProjet.objects.create(
            company=self.co, budget=budget,
            categorie=LigneBudgetProjet.Categorie.MAIN_OEUVRE,
            libelle='MO', montant_prevu=Decimal('5000'))

    def _ajouter_cout_reel(self, montant_charge_jours, cout_horaire=Decimal('100')):
        tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1,
            avancement_pct=50)
        ressource = RessourceProfil.objects.create(
            company=self.co, nom='R', cout_horaire=cout_horaire)
        AffectationRessource.objects.create(
            company=self.co, tache=tache, ressource=ressource,
            date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 2),
            charge_jours=montant_charge_jours)
        return tache

    def test_cpi_absent_etc_egal_budget_restant(self):
        # Aucun coût réel → AC = 0 → CPI None (division par zéro gardée).
        data = selectors.prevision_fin_projet(self.projet)
        self.assertIsNone(data['cpi'])
        ligne_mo = next(
            ligne for ligne in data['par_categorie']
            if ligne['categorie'] == LigneBudgetProjet.Categorie.MAIN_OEUVRE)
        # budget_restant = 5000 - 0 = 5000, non ajusté.
        self.assertEqual(ligne_mo['etc'], Decimal('5000'))
        self.assertEqual(ligne_mo['eac'], Decimal('5000'))

    def test_cpi_egal_1_eac_egal_budget(self):
        # Avancement 50 % × budget_total 10000 = EV 5000 ; réel MO = 5000 ×
        # 8h × ... choisi pour AC ≈ EV → CPI ≈ 1.
        self._ajouter_cout_reel(Decimal('6.25'))  # 6.25j × 8h × 100 = 5000
        data = selectors.prevision_fin_projet(self.projet)
        self.assertIsNotNone(data['cpi'])
        self.assertAlmostEqual(float(data['cpi']), 1.0, places=2)
        ligne_mo = next(
            ligne for ligne in data['par_categorie']
            if ligne['categorie'] == LigneBudgetProjet.Categorie.MAIN_OEUVRE)
        # budget_restant = 5000 - 5000 = 0 → ETC = 0 / CPI = 0.
        self.assertEqual(ligne_mo['etc'], Decimal('0.00'))
        self.assertEqual(ligne_mo['eac'], Decimal('5000.00'))

    def test_cpi_superieur_1_sous_consommation(self):
        # CPI > 1 signifie qu'on dépense MOINS que prévu pour l'avancement
        # atteint → ETC divisé par un nombre > 1 → ETC plus petit.
        self._ajouter_cout_reel(Decimal('3'))  # 3j × 8h × 100 = 2400
        data = selectors.prevision_fin_projet(self.projet)
        self.assertGreater(data['cpi'], Decimal('1'))
        ligne_mo = next(
            ligne for ligne in data['par_categorie']
            if ligne['categorie'] == LigneBudgetProjet.Categorie.MAIN_OEUVRE)
        budget_restant = Decimal('5000') - ligne_mo['reel']
        self.assertLess(ligne_mo['etc'], budget_restant)

    def test_cpi_inferieur_1_surconsommation(self):
        # CPI < 1 : on dépense PLUS que prévu pour l'avancement atteint →
        # ETC divisé par un nombre < 1 → ETC plus grand que le restant brut.
        self._ajouter_cout_reel(Decimal('10'))  # 10j × 8h × 100 = 8000
        data = selectors.prevision_fin_projet(self.projet)
        self.assertLess(data['cpi'], Decimal('1'))
        ligne_mo = next(
            ligne for ligne in data['par_categorie']
            if ligne['categorie'] == LigneBudgetProjet.Categorie.MAIN_OEUVRE)
        budget_restant = Decimal('5000') - ligne_mo['reel']
        self.assertGreater(ligne_mo['etc'], budget_restant)

    def test_endpoint_scope_societe(self):
        api = auth(self.user)
        resp = api.get(
            f'/api/django/gestion-projet/projets/{self.projet.id}/'
            f'prevision-fin/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('par_categorie', resp.data)
        self.assertIn('eac_total', resp.data)

    def test_endpoint_404_autre_societe(self):
        autre_co = make_company('gp-xprj16-autre', 'Autre')
        autre_user = make_user(autre_co, 'user-autre-x16')
        api = auth(autre_user)
        resp = api.get(
            f'/api/django/gestion-projet/projets/{self.projet.id}/'
            f'prevision-fin/')
        self.assertEqual(resp.status_code, 404)

    def test_portail_client_aucun_montant_interne(self):
        # Garde-fou : le portail client (PROJ37) reste inchangé et n'expose
        # jamais de montant ETC/EAC.
        data = selectors.portail_avancement_client(self.projet)
        serialise = str(data)
        self.assertNotIn('eac', serialise.lower())
        self.assertNotIn('etc', serialise.lower())
