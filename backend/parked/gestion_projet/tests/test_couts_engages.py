"""Tests PROJ22 — Coûts engagés/réels vs budget prévisionnel (PROJ21).

Couvre :
- le sélecteur ``couts_engages_vs_reels`` : budget (PROJ21) vs réel par
  catégorie, main-d'œuvre RÉELLE issue des affectations internes
  (charge_jours × coût horaire × 8 h/j), écart (budget − réel) + écart %
  (None quand budget == 0 — garde division-par-zéro) ;
- la dégradation propre des sources factures fournisseur/achats (réel = 0 +
  note quand un ``ProjetLien`` est rattaché mais sans montant exploitable, et
  réel = 0 + note quand aucune source) ;
- le choix du budget de référence (``budget_effectif`` : validé le plus récent,
  sinon le plus récent ; projet sans budget → tout à 0) ;
- le scoping multi-société (réel/budget isolés par société) ;
- l'endpoint ``projets/{id}/couts-engages-reels/`` (200, payload, cross-tenant
  404, rôle ``normal`` → 403).

Aucune app externe n'est importée : la main-d'œuvre est 100 % interne ; les
factures fournisseur/achats sont rattachées via ``ProjetLien`` (référence
lâche) et dégradent proprement (frontière cross-app, CLAUDE.md).
"""
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


def make_projet(company, code='P22'):
    return Projet.objects.create(company=company, code=code, nom='Projet P22')


def make_budget(company, projet, **kw):
    return BudgetProjet.objects.create(company=company, projet=projet, **kw)


def make_ligne(company, budget, categorie, montant):
    return LigneBudgetProjet.objects.create(
        company=company, budget=budget, categorie=categorie,
        libelle=f'{categorie} ligne', montant_prevu=Decimal(montant))


def make_affectation(company, projet, cout_horaire, charge_jours,
                     nom='Technicien'):
    tache = Tache.objects.create(
        company=company, projet=projet, libelle='Tâche MO')
    ressource = RessourceProfil.objects.create(
        company=company, nom=nom, cout_horaire=Decimal(cout_horaire))
    return AffectationRessource.objects.create(
        company=company, tache=tache, ressource=ressource,
        date_debut='2026-07-01', date_fin='2026-07-05',
        charge_jours=Decimal(charge_jours))


def cat(rows, categorie):
    return next(r for r in rows if r['categorie'] == categorie)


class CoutsEngagesSelectorTests(TestCase):
    """Sélecteur ``couts_engages_vs_reels`` — budget vs réel par catégorie."""

    def setUp(self):
        self.co = make_company('proj22-sel', 'Societe S')
        self.projet = make_projet(self.co, 'P22-SEL')
        self.budget = make_budget(self.co, self.projet, statut='valide')
        make_ligne(self.co, self.budget, 'materiel', '1000.00')
        make_ligne(self.co, self.budget, 'main_oeuvre', '2000.00')
        make_ligne(self.co, self.budget, 'sous_traitance', '500.00')

    def test_budget_per_category_present(self):
        data = selectors.couts_engages_vs_reels(self.co, self.projet)
        mat = cat(data['par_categorie'], 'materiel')
        mo = cat(data['par_categorie'], 'main_oeuvre')
        st = cat(data['par_categorie'], 'sous_traitance')
        div = cat(data['par_categorie'], 'divers')
        self.assertEqual(mat['budget'], Decimal('1000.00'))
        self.assertEqual(mo['budget'], Decimal('2000.00'))
        self.assertEqual(st['budget'], Decimal('500.00'))
        # toutes les catégories canoniques sont présentes (divers à 0).
        self.assertEqual(div['budget'], Decimal('0'))

    def test_main_oeuvre_reelle_from_affectations(self):
        # 2 jours-homme × 50 MAD/h × 8 h/j = 800 MAD de réel main-d'œuvre.
        make_affectation(self.co, self.projet, '50.00', '2.00')
        data = selectors.couts_engages_vs_reels(self.co, self.projet)
        mo = cat(data['par_categorie'], 'main_oeuvre')
        self.assertEqual(mo['reel'], Decimal('800.00'))
        # écart = budget − réel = 2000 − 800 = 1200.
        self.assertEqual(mo['ecart'], Decimal('1200.00'))
        # écart % = 1200 / 2000 × 100 = 60.00.
        self.assertEqual(mo['ecart_pct'], Decimal('60.00'))

    def test_main_oeuvre_reelle_accumulates(self):
        make_affectation(self.co, self.projet, '50.00', '2.00', nom='Tech A')
        make_affectation(self.co, self.projet, '100.00', '1.00', nom='Tech B')
        data = selectors.couts_engages_vs_reels(self.co, self.projet)
        mo = cat(data['par_categorie'], 'main_oeuvre')
        # 800 + (1 × 8 × 100) = 800 + 800 = 1600.
        self.assertEqual(mo['reel'], Decimal('1600.00'))

    def test_materiel_sous_traitance_degrade_zero_with_note(self):
        # aucun lien facture/achat → réel 0 + note.
        data = selectors.couts_engages_vs_reels(self.co, self.projet)
        mat = cat(data['par_categorie'], 'materiel')
        st = cat(data['par_categorie'], 'sous_traitance')
        self.assertEqual(mat['reel'], Decimal('0'))
        self.assertEqual(st['reel'], Decimal('0'))
        self.assertTrue(mat['note'])
        self.assertTrue(st['note'])

    def test_facture_lien_counted_with_note(self):
        ProjetLien.objects.create(
            company=self.co, projet=self.projet, type_cible='facture',
            cible_id=1, libelle='Facture fournisseur')
        ProjetLien.objects.create(
            company=self.co, projet=self.projet, type_cible='achat',
            cible_id=2, libelle='Achat')
        data = selectors.couts_engages_vs_reels(self.co, self.projet)
        self.assertEqual(data['nb_liens_depense'], 2)
        mat = cat(data['par_categorie'], 'materiel')
        # réel reste 0 (montant non exploitable) mais la note mentionne les liens.
        self.assertEqual(mat['reel'], Decimal('0'))
        self.assertIn('2', mat['note'])

    def test_devis_lien_not_counted_as_depense(self):
        # un lien devis n'est PAS une dépense engagée.
        ProjetLien.objects.create(
            company=self.co, projet=self.projet, type_cible='devis',
            cible_id=9, libelle='Devis')
        data = selectors.couts_engages_vs_reels(self.co, self.projet)
        self.assertEqual(data['nb_liens_depense'], 0)

    def test_ecart_pct_none_when_budget_zero(self):
        # divers n'a aucune ligne budget → budget 0 → écart % None.
        data = selectors.couts_engages_vs_reels(self.co, self.projet)
        div = cat(data['par_categorie'], 'divers')
        self.assertEqual(div['budget'], Decimal('0'))
        self.assertIsNone(div['ecart_pct'])
        # l'écart absolu reste calculé (0 − 0 = 0).
        self.assertEqual(div['ecart'], Decimal('0'))

    def test_total_aggregates_all_categories(self):
        make_affectation(self.co, self.projet, '50.00', '2.00')
        data = selectors.couts_engages_vs_reels(self.co, self.projet)
        # budget total = 1000 + 2000 + 500 = 3500 ; réel total = 800 (MO).
        self.assertEqual(data['total']['budget'], Decimal('3500.00'))
        self.assertEqual(data['total']['reel'], Decimal('800.00'))
        self.assertEqual(data['total']['ecart'], Decimal('2700.00'))
        # 2700 / 3500 × 100 = 77.14 (arrondi 2 décimales).
        self.assertEqual(data['total']['ecart_pct'], Decimal('77.14'))

    def test_total_ecart_pct_none_when_no_budget(self):
        projet = make_projet(self.co, 'P22-NOBUD')
        data = selectors.couts_engages_vs_reels(self.co, projet)
        self.assertEqual(data['total']['budget'], Decimal('0'))
        self.assertIsNone(data['total']['ecart_pct'])
        self.assertIsNone(data['budget_id'])


class BudgetEffectifTests(TestCase):
    """Choix du budget de référence (``budget_effectif``)."""

    def setUp(self):
        self.co = make_company('proj22-eff', 'Societe E')
        self.projet = make_projet(self.co, 'P22-EFF')

    def test_no_budget_returns_none(self):
        self.assertIsNone(selectors.budget_effectif(self.projet))

    def test_prefers_latest_validated(self):
        make_budget(self.co, self.projet, version=1, statut='valide')
        b2 = make_budget(self.co, self.projet, version=2, statut='valide')
        # un brouillon de version supérieure ne doit pas masquer le validé.
        make_budget(self.co, self.projet, version=3, statut='brouillon')
        self.assertEqual(selectors.budget_effectif(self.projet).id, b2.id)

    def test_falls_back_to_latest_when_no_validated(self):
        make_budget(self.co, self.projet, version=1, statut='brouillon')
        b2 = make_budget(self.co, self.projet, version=2, statut='brouillon')
        self.assertEqual(selectors.budget_effectif(self.projet).id, b2.id)


class CoutsEngagesScopingTests(TestCase):
    """Isolation multi-société du réel et du budget."""

    def test_mo_reelle_scoped_to_company(self):
        co_a = make_company('proj22-sc-a', 'A')
        co_b = make_company('proj22-sc-b', 'B')
        projet_a = make_projet(co_a, 'P22-A')
        make_budget(co_a, projet_a, statut='valide')
        make_affectation(co_a, projet_a, '50.00', '2.00')
        # une affectation d'une AUTRE société sur un AUTRE projet ne compte pas.
        projet_b = make_projet(co_b, 'P22-B')
        make_affectation(co_b, projet_b, '999.00', '999.00', nom='Etranger')
        data = selectors.couts_engages_vs_reels(co_a, projet_a)
        mo = cat(data['par_categorie'], 'main_oeuvre')
        self.assertEqual(mo['reel'], Decimal('800.00'))


class CoutsEngagesEndpointTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('proj22-ep-a', 'A')
        self.co_b = make_company('proj22-ep-b', 'B')
        self.user_a = make_user(self.co_a, 'proj22-ep-a')
        self.user_b = make_user(self.co_b, 'proj22-ep-b')
        self.projet_a = make_projet(self.co_a, 'P22-EPA')
        self.budget_a = make_budget(self.co_a, self.projet_a, statut='valide')
        make_ligne(self.co_a, self.budget_a, 'main_oeuvre', '2000.00')
        make_affectation(self.co_a, self.projet_a, '50.00', '2.00')

    def _url(self, projet):
        return f'{self.BASE}{projet.id}/couts-engages-reels/'

    def test_endpoint_returns_200_and_payload(self):
        resp = auth(self.user_a).get(self._url(self.projet_a))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['budget_id'], self.budget_a.id)
        mo = cat(resp.data['par_categorie'], 'main_oeuvre')
        # montants sérialisés en chaînes (comme l'action ``total``).
        self.assertEqual(mo['budget'], '2000.00')
        self.assertEqual(mo['reel'], '800.00')
        self.assertEqual(mo['ecart'], '1200.00')
        self.assertEqual(mo['ecart_pct'], '60.00')
        self.assertEqual(resp.data['total']['reel'], '800.00')

    def test_endpoint_ecart_pct_none_serialized_as_null(self):
        resp = auth(self.user_a).get(self._url(self.projet_a))
        self.assertEqual(resp.status_code, 200, resp.data)
        # divers n'a pas de budget → écart % None → JSON null.
        div = cat(resp.data['par_categorie'], 'divers')
        self.assertIsNone(div['ecart_pct'])

    def test_endpoint_cross_tenant_404(self):
        resp = auth(self.user_b).get(self._url(self.projet_a))
        self.assertEqual(resp.status_code, 404)

    def test_endpoint_role_normal_refuse(self):
        normal = make_user(self.co_a, 'proj22-ep-normal', role='normal')
        resp = auth(normal).get(self._url(self.projet_a))
        self.assertEqual(resp.status_code, 403)
