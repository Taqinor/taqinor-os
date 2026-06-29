"""
FG294 — Budget projet vs réel (engagé/dépensé) — ``BudgetProjet`` /
``BudgetEngagement`` + sélecteur ``budget_projet_synthese``.

Couvre :
  * la création d'un budget (société posée côté serveur, refus du programme
    d'une autre société, seuil d'alerte borné) ;
  * le rattachement d'un coût fournisseur (BCF ou facture) à un budget
    (validation source↔cible, scope société de l'objet stock) ;
  * l'AGRÉGATION du réel par le sélecteur : devis du programme, engagé (BCF
    commandés), dépensé (factures fournisseur), main-d'œuvre des chantiers
    (jours réels × tarif) ;
  * l'alerte de DÉPASSEMENT (total > budget × (1 + seuil)) et le repérage des
    catégories dépassées ;
  * le scope société (isolation + endpoint synthèse).

Le sélecteur lit les apps ``ventes``/``stock`` sans importer leurs modèles
(``apps.get_model`` + ``apps.stock.selectors``) — import-linter safe.

Run :
    python manage.py test apps.installations.tests_fg294_budget -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import (
    Produit, Fournisseur, BonCommandeFournisseur,
    LigneBonCommandeFournisseur, FactureFournisseur,
)
from apps.installations.models import (
    Projet, ProjetChantier, ProjetDevis, BudgetProjet, BudgetEngagement,
    Installation,
)
from apps.installations.selectors import budget_projet_synthese

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg294-co-{n}', defaults={'nom': nom or f'FG294 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'fg294-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Ferme', prenom='Client',
        email=f'fg294-{company.id}-{n}@example.invalid')


def make_projet(company, reference=None):
    n = next(_seq)
    return Projet.objects.create(
        company=company, reference=reference or f'PRG-B-{n}',
        nom='Ferme 4 forages', client=make_client(company))


def make_produit(company, prix_achat='100', prix_vente='150'):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=f'Panneau {n}', sku=f'SKU-{company.id}-{n}',
        prix_achat=Decimal(prix_achat), prix_vente=Decimal(prix_vente),
        quantite_stock=100)


def make_bcf(company, produit, quantite, prix_achat_unitaire):
    n = next(_seq)
    four = Fournisseur.objects.create(company=company, nom=f'Four {n}')
    bcf = BonCommandeFournisseur.objects.create(
        company=company, reference=f'BCF-{company.id}-{n}', fournisseur=four)
    LigneBonCommandeFournisseur.objects.create(
        bon_commande=bcf, produit=produit, quantite=quantite,
        prix_achat_unitaire=Decimal(str(prix_achat_unitaire)))
    return bcf


def make_facture(company, montant_ht):
    n = next(_seq)
    four = Fournisseur.objects.create(company=company, nom=f'FourF {n}')
    return FactureFournisseur.objects.create(
        company=company, reference=f'FF-{company.id}-{n}', fournisseur=four,
        montant_ht=Decimal(str(montant_ht)),
        montant_ttc=Decimal(str(montant_ht)) * Decimal('1.2'))


def attach_devis(company, projet, lignes):
    """lignes = [(designation, quantite, prix_unitaire), ...] → Devis + lien."""
    n = next(_seq)
    devis = Devis.objects.create(
        company=company, reference=f'DEV-B-{company.id}-{n}',
        client=projet.client, taux_tva=Decimal('20'))
    produit = make_produit(company)
    for designation, qte, pu in lignes:
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=designation,
            quantite=Decimal(str(qte)), prix_unitaire=Decimal(str(pu)))
    ProjetDevis.objects.create(company=company, projet=projet, devis=devis)
    return devis


def attach_chantier(company, projet, labour_jours_reels):
    n = next(_seq)
    inst = Installation.objects.create(
        company=company, reference=f'CH-{company.id}-{n}',
        client=projet.client,
        labour_jours_reels=Decimal(str(labour_jours_reels)))
    ProjetChantier.objects.create(
        company=company, projet=projet, installation=inst)
    return inst


# ── Création du budget ────────────────────────────────────────────────────────

class TestFG294BudgetCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.projet = make_projet(self.company)

    def test_create_sets_company_server_side(self):
        """FG294 — le budget porte la société du user (jamais lue du corps)."""
        other = make_company()
        r = self.api.post(f'{BASE}/programme-budgets/', {
            'projet': self.projet.id,
            'budget_materiel': '10000',
            'budget_main_oeuvre': '3000',
            'company': other.id,  # ignoré côté serveur
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        budget = BudgetProjet.objects.get(id=r.data['id'])
        self.assertEqual(budget.company_id, self.company.id)
        self.assertEqual(budget.created_by_id, self.user.id)
        self.assertEqual(r.data['budget_total'], 13000.0)

    def test_create_rejects_cross_company_projet(self):
        """FG294 — impossible de budgéter le programme d'une autre société."""
        other = make_company()
        projet_b = make_projet(other)
        r = self.api.post(
            f'{BASE}/programme-budgets/',
            {'projet': projet_b.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_seuil_alerte_bounded(self):
        """FG294 — le seuil d'alerte est borné [0, 100] %."""
        r = self.api.post(
            f'{BASE}/programme-budgets/',
            {'projet': self.projet.id, 'seuil_alerte_pct': '150'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)


# ── Rattachement d'un coût fournisseur ────────────────────────────────────────

class TestFG294Engagement(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.projet = make_projet(self.company)
        self.budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet)
        self.produit = make_produit(self.company)

    def test_attach_bcf_engagement(self):
        """FG294 — un BCF se rattache au budget (source = bon de commande)."""
        bcf = make_bcf(self.company, self.produit, 10, '100')
        r = self.api.post(f'{BASE}/programme-engagements/', {
            'budget': self.budget.id,
            'source': 'bon_commande',
            'categorie': 'materiel',
            'bon_commande': bcf.id,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        eng = BudgetEngagement.objects.get(id=r.data['id'])
        self.assertEqual(eng.company_id, self.company.id)
        self.assertEqual(eng.bon_commande_id, bcf.id)

    def test_bcf_source_requires_bcf(self):
        """FG294 — un engagement « bon de commande » sans BCF est refusé."""
        r = self.api.post(f'{BASE}/programme-engagements/', {
            'budget': self.budget.id, 'source': 'bon_commande',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_facture_source_rejects_bcf(self):
        """FG294 — un engagement « facture » ne doit pas porter un BCF."""
        bcf = make_bcf(self.company, self.produit, 1, '1')
        facture = make_facture(self.company, '500')
        r = self.api.post(f'{BASE}/programme-engagements/', {
            'budget': self.budget.id, 'source': 'facture',
            'facture': facture.id, 'bon_commande': bcf.id,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_cross_company_bcf_rejected(self):
        """FG294 — un BCF d'une autre société ne peut pas être rattaché."""
        other = make_company()
        prod_b = make_produit(other)
        bcf_b = make_bcf(other, prod_b, 1, '1')
        r = self.api.post(f'{BASE}/programme-engagements/', {
            'budget': self.budget.id, 'source': 'bon_commande',
            'bon_commande': bcf_b.id,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)


# ── Agrégation du réel (sélecteur) ────────────────────────────────────────────

class TestFG294Synthese(TestCase):
    def setUp(self):
        self.company = make_company()
        self.projet = make_projet(self.company)
        self.produit = make_produit(self.company)

    def test_engage_from_bcf_ordered_amount(self):
        """FG294 — l'engagé matériel = Σ montants COMMANDÉS des BCF rattachés."""
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet,
            budget_materiel=Decimal('5000'))
        bcf = make_bcf(self.company, self.produit, 10, '100')  # 10×100 = 1000
        BudgetEngagement.objects.create(
            company=self.company, budget=budget,
            source=BudgetEngagement.Source.BON_COMMANDE,
            categorie=BudgetEngagement.Categorie.MATERIEL, bon_commande=bcf)
        res = budget_projet_synthese(budget)
        self.assertEqual(res['engage']['materiel'], 1000.0)
        self.assertEqual(res['engage']['total'], 1000.0)
        # Pas de facture → dépensé matériel à 0.
        self.assertEqual(res['depense']['materiel'], 0.0)

    def test_depense_from_facture_ht(self):
        """FG294 — le dépensé = Σ montants HT des factures fournisseur."""
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet,
            budget_materiel=Decimal('5000'))
        facture = make_facture(self.company, '2500')
        BudgetEngagement.objects.create(
            company=self.company, budget=budget,
            source=BudgetEngagement.Source.FACTURE,
            categorie=BudgetEngagement.Categorie.MATERIEL, facture=facture)
        res = budget_projet_synthese(budget)
        self.assertEqual(res['depense']['materiel'], 2500.0)
        self.assertEqual(res['depense']['total'], 2500.0)
        self.assertEqual(res['reste'], 2500.0)  # 5000 − 2500

    def test_main_oeuvre_from_chantiers(self):
        """FG294 — la main-d'œuvre réelle = Σ jours réels × tarif, en engagé ET
        dépensé sur la catégorie main_oeuvre."""
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet,
            budget_main_oeuvre=Decimal('4000'),
            tarif_jour_mo=Decimal('500'))
        attach_chantier(self.company, self.projet, labour_jours_reels='3')
        attach_chantier(self.company, self.projet, labour_jours_reels='2')
        res = budget_projet_synthese(budget)
        # (3 + 2) jours × 500 = 2500
        self.assertEqual(res['main_oeuvre_jours_reels'], 5.0)
        self.assertEqual(res['depense']['main_oeuvre'], 2500.0)
        self.assertEqual(res['engage']['main_oeuvre'], 2500.0)

    def test_devis_total_aggregated(self):
        """FG294 — le montant contracté client = Σ totaux des devis du
        programme (lecture cross-app sans import du modèle ventes)."""
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet)
        attach_devis(self.company, self.projet,
                     [('Kit', 1, '1000'), ('Pose', 1, '500')])  # HT 1500
        res = budget_projet_synthese(budget)
        self.assertEqual(res['devis_total_ht'], 1500.0)
        # TTC = 1500 × 1.20 = 1800
        self.assertEqual(res['devis_total_ttc'], 1800.0)

    def test_overbudget_alert_flag(self):
        """FG294 — dépassement quand le dépensé total > budget × (1 + seuil)."""
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet,
            budget_materiel=Decimal('1000'),
            seuil_alerte_pct=Decimal('10'))  # plafond = 1100
        facture = make_facture(self.company, '1200')  # > 1100
        BudgetEngagement.objects.create(
            company=self.company, budget=budget,
            source=BudgetEngagement.Source.FACTURE,
            categorie=BudgetEngagement.Categorie.MATERIEL, facture=facture)
        res = budget_projet_synthese(budget)
        self.assertTrue(res['depassement'])
        self.assertIn('materiel', res['categories_depassees'])
        self.assertEqual(res['reste'], -200.0)  # 1000 − 1200

    def test_within_threshold_no_alert(self):
        """FG294 — pas d'alerte tant que le dépensé reste sous le plafond."""
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet,
            budget_materiel=Decimal('1000'),
            seuil_alerte_pct=Decimal('20'))  # plafond = 1200
        facture = make_facture(self.company, '1100')  # ≤ 1200
        BudgetEngagement.objects.create(
            company=self.company, budget=budget,
            source=BudgetEngagement.Source.FACTURE,
            categorie=BudgetEngagement.Categorie.MATERIEL, facture=facture)
        res = budget_projet_synthese(budget)
        self.assertFalse(res['depassement'])
        # La catégorie matériel reste dépassée (1100 > 1000) même sans alerte
        # globale — l'info fine est conservée.
        self.assertIn('materiel', res['categories_depassees'])

    def test_zero_budget_never_alerts(self):
        """FG294 — un budget total nul ne déclenche jamais l'alerte (évite la
        division/le faux positif sur un budget non saisi)."""
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet)
        facture = make_facture(self.company, '500')
        BudgetEngagement.objects.create(
            company=self.company, budget=budget,
            source=BudgetEngagement.Source.FACTURE,
            categorie=BudgetEngagement.Categorie.MATERIEL, facture=facture)
        res = budget_projet_synthese(budget)
        self.assertFalse(res['depassement'])


# ── Scope société ─────────────────────────────────────────────────────────────

class TestFG294Tenant(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.projet = make_projet(self.company)
        self.budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet)

    def test_company_isolation(self):
        """FG294 — la société B ne voit pas les budgets de A."""
        company_b = make_company()
        user_b = make_user(company_b)
        r = auth(user_b).get(f'{BASE}/programme-budgets/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_synthese_endpoint(self):
        """FG294 — l'endpoint synthèse renvoie budget vs réel + alerte."""
        produit = make_produit(self.company)
        bcf = make_bcf(self.company, produit, 5, '100')  # engagé 500
        BudgetEngagement.objects.create(
            company=self.company, budget=self.budget,
            source=BudgetEngagement.Source.BON_COMMANDE,
            categorie=BudgetEngagement.Categorie.MATERIEL, bon_commande=bcf)
        r = self.api.get(
            f'{BASE}/programme-budgets/{self.budget.id}/synthese/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['engage']['materiel'], 500.0)
        self.assertIn('depassement', r.data)
        self.assertIn('reste', r.data)

    def test_synthese_other_company_404(self):
        """FG294 — la synthèse d'un budget d'une autre société est inaccessible."""
        company_b = make_company()
        user_b = make_user(company_b)
        r = auth(user_b).get(
            f'{BASE}/programme-budgets/{self.budget.id}/synthese/')
        self.assertEqual(r.status_code, 404)
