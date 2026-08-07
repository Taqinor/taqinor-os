"""PACT163 — trois capacités XACC cochées sans aucune vue (XACC15/16/22).

Constat qui a motivé la tâche : ``etaler_charge_avance`` (XACC15),
``generer_dotations_derogatoires`` (XACC16) et ``generer_ligne_budget_
repartie`` (XACC22) — ``apps/compta/services.py`` — n'avaient ni appelant
hors tests ni route : charges constatées d'avance, double plan comptable/
fiscal et budget par courbe de répartition n'existaient que comme fonctions,
inatteignables par l'API malgré leurs tâches d'origine cochées.

Ce module vérifie chaque capacité désormais DÉCLENCHABLE via son ViewSet :
  * XACC15 — ``POST /compta/charges-avance/`` (``ChargeConstateeAvanceViewSet``,
    écran ``ChargesAvancePage.jsx``) ;
  * XACC16 — ``POST /compta/immobilisations/<id>/plan-fiscal/`` (action sur
    ``ImmobilisationViewSet``, écran ``ImmobilisationsPage.jsx`` — bouton
    « Plan fiscal (dérogatoire) ») ;
  * XACC22 — ``POST /compta/budgets/<id>/generer-ligne-repartie/`` (action sur
    ``BudgetViewSet``, écran ``BudgetsPage.jsx``).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    BudgetLigne, ChargeConstateeAvance, DotationDerogatoire,
    Immobilisation, PlanAmortissementFiscal,
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


def make_immo(company, **kwargs):
    defaults = dict(
        libelle='Onduleur central', categorie=Immobilisation.Categorie.MATERIEL,
        cout=Decimal('100000'), taux_tva=Decimal('20.00'),
        date_acquisition=date(2026, 1, 1))
    defaults.update(kwargs)
    return Immobilisation.objects.create(company=company, **defaults)


# ── XACC15 — Charges constatées d'avance ────────────────────────────────────

class ChargeConstateeAvanceApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('pact163-cca-a', 'PACT163 CCA A')
        self.co_b = make_company('pact163-cca-b', 'PACT163 CCA B')
        self.user_a = make_user(self.co_a, 'pact163-cca-user-a')
        self.user_b = make_user(self.co_b, 'pact163-cca-user-b')

    def test_creation_via_api_pose_company_et_genere_les_dotations(self):
        api = auth(self.user_a)
        resp = api.post('/api/django/compta/charges-avance/', {
            'libelle': 'Assurance flotte annuelle',
            'montant_total': '12000.00',
            'date_debut': '2026-01-01',
            'nb_mois': 12,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        charge = ChargeConstateeAvance.objects.get(id=resp.data['id'])
        self.assertEqual(charge.company, self.co_a)  # posée côté serveur.
        self.assertEqual(len(resp.data['dotations']), 12)
        total = sum(Decimal(str(d['montant'])) for d in resp.data['dotations'])
        self.assertEqual(total, Decimal('12000.00'))

    def test_montant_total_negatif_refuse(self):
        api = auth(self.user_a)
        resp = api.post('/api/django/compta/charges-avance/', {
            'libelle': 'Invalide', 'montant_total': '-100.00',
            'date_debut': '2026-01-01', 'nb_mois': 3,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_liste_isolee_par_societe(self):
        services.etaler_charge_avance(
            self.co_a, montant_total=Decimal('6000'), date_debut=date(2026, 1, 1),
            nb_mois=6, libelle='CCA société A')
        services.etaler_charge_avance(
            self.co_b, montant_total=Decimal('6000'), date_debut=date(2026, 1, 1),
            nb_mois=6, libelle='CCA société B')
        resp = auth(self.user_a).get('/api/django/compta/charges-avance/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['libelle'], 'CCA société A')

    def test_acces_refuse_role_normal(self):
        normal = make_user(self.co_a, 'pact163-cca-normal', role='normal')
        resp = auth(normal).get('/api/django/compta/charges-avance/')
        self.assertEqual(resp.status_code, 403)


# ── XACC16 — Amortissements dérogatoires (plan fiscal parallèle) ───────────

class PlanFiscalApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('pact163-fisc-a', 'PACT163 Fisc A')
        self.co_b = make_company('pact163-fisc-b', 'PACT163 Fisc B')
        self.user_a = make_user(self.co_a, 'pact163-fisc-user-a')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
        self.immo_a = make_immo(self.co_a, cout=Decimal('100000'))

    def _url(self, immo):
        return f'/api/django/compta/immobilisations/{immo.id}/plan-fiscal/'

    def test_post_sans_plan_comptable_refuse(self):
        api = auth(self.user_a)
        resp = api.post(self._url(self.immo_a), {'duree_annees': 5}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_get_404_avant_generation(self):
        services.generer_plan_amortissement(
            self.immo_a, mode='lineaire', duree_annees=5)
        resp = auth(self.user_a).get(self._url(self.immo_a))
        self.assertEqual(resp.status_code, 404)

    def test_post_genere_le_plan_fiscal_et_ses_dotations_derogatoires(self):
        services.generer_plan_amortissement(
            self.immo_a, mode='lineaire', duree_annees=5)
        api = auth(self.user_a)
        resp = api.post(
            self._url(self.immo_a),
            {'mode': 'degressif', 'duree_annees': 5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        plan_fiscal = PlanAmortissementFiscal.objects.get(id=resp.data['id'])
        self.assertEqual(plan_fiscal.company, self.co_a)  # posée côté serveur.
        self.assertEqual(
            DotationDerogatoire.objects.filter(plan_fiscal=plan_fiscal).count(), 5)
        self.assertEqual(len(resp.data['dotations_derogatoires']), 5)

        # Désormais joignable en GET (plus 404).
        resp_get = api.get(self._url(self.immo_a))
        self.assertEqual(resp_get.status_code, 200)
        self.assertEqual(resp_get.data['id'], plan_fiscal.id)

    def test_plan_fiscal_cross_company_404(self):
        services.seed_plan_comptable(self.co_b)
        immo_b = make_immo(self.co_b, cout=Decimal('50000'))
        services.generer_plan_amortissement(
            immo_b, mode='lineaire', duree_annees=5)
        api_a = auth(self.user_a)
        resp = api_a.post(
            self._url(immo_b), {'duree_annees': 5}, format='json')
        self.assertEqual(resp.status_code, 404)


# ── XACC22 — Budget : ligne générée par courbe de répartition ──────────────

class BudgetLigneRepartieApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('pact163-bud-a', 'PACT163 Budget A')
        self.co_b = make_company('pact163-bud-b', 'PACT163 Budget B')
        self.user_a = make_user(self.co_a, 'pact163-bud-user-a')
        for co in (self.co_a, self.co_b):
            services.seed_plan_comptable(co)
        self.budget_a = services.creer_budget(self.co_a, annee=2026)
        self.compte_a = services._assurer_compte(self.co_a, '6132')

    def _url(self, budget):
        return f'/api/django/compta/budgets/{budget.id}/generer-ligne-repartie/'

    def test_repartition_egale_somme_le_montant_annuel(self):
        api = auth(self.user_a)
        resp = api.post(self._url(self.budget_a), {
            'compte': self.compte_a.id, 'montant_annuel': '1200.00',
            'courbe': 'egale',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ligne = BudgetLigne.objects.get(
            budget=self.budget_a, compte=self.compte_a)
        total = sum(
            (getattr(ligne, m) for m in BudgetLigne.MOIS), Decimal('0'))
        self.assertEqual(total, Decimal('1200.00'))
        self.assertEqual(ligne.m01, Decimal('100.00'))  # 1200 / 12, égale.

    def test_courbe_saisonniere_egalement_exacte(self):
        api = auth(self.user_a)
        resp = api.post(self._url(self.budget_a), {
            'compte': self.compte_a.id, 'montant_annuel': '10000.00',
            'courbe': 'saisonniere',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ligne = BudgetLigne.objects.get(
            budget=self.budget_a, compte=self.compte_a)
        total = sum(
            (getattr(ligne, m) for m in BudgetLigne.MOIS), Decimal('0'))
        self.assertEqual(total, Decimal('10000.00'))

    def test_compte_d_une_autre_societe_refuse(self):
        compte_b = services._assurer_compte(self.co_b, '6132')
        api_a = auth(self.user_a)
        resp = api_a.post(self._url(self.budget_a), {
            'compte': compte_b.id, 'montant_annuel': '1000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_budget_cross_company_404(self):
        budget_b = services.creer_budget(self.co_b, annee=2026)
        api_a = auth(self.user_a)
        resp = api_a.post(self._url(budget_b), {
            'compte': self.compte_a.id, 'montant_annuel': '1000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_acces_refuse_role_normal(self):
        normal = make_user(self.co_a, 'pact163-bud-normal', role='normal')
        resp = auth(normal).post(self._url(self.budget_a), {
            'compte': self.compte_a.id, 'montant_annuel': '1000.00',
        }, format='json')
        self.assertEqual(resp.status_code, 403)


# ── Non-régression : le routeur compta ne double plus rien (garde PACT26) ──

class RegistreVerification(TestCase):
    def test_les_trois_ressources_sont_bien_dans_le_routeur_compta(self):
        from apps.compta.urls import router as router_compta

        prefixes = {p for p, _, _ in router_compta.registry}
        self.assertIn('charges-avance', prefixes)
        self.assertIn('budgets', prefixes)
        self.assertIn('immobilisations', prefixes)
