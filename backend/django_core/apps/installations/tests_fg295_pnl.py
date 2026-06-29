"""
FG295 — P&L de projet consolidé — sélecteur ``projet_pnl`` + action
``ProjetViewSet.pnl``.

Le P&L consolide, pour UN ``Projet``, le résultat de TOUS ses chantiers :
REVENU (factures CLIENT émises sur les devis du programme) − COÛTS (matériel
via factures fournisseur, sous-traitance, imports/divers, main-d'œuvre des
chantiers) → marge brute + marge %.

Couvre :
  * le revenu = Σ factures client des devis du programme (HT/TTC), factures
    ANNULÉES exclues ;
  * les coûts réels (dépensé fournisseur ventilé + main-d'œuvre des chantiers),
    réutilisant l'agrégation FG294 ;
  * la marge brute (revenu HT − coûts) et la marge % (0 si revenu nul) ;
  * la dégradation propre (programme sans budget / sans facture → 0) ;
  * le scope société (isolation : aucune facture/coût d'une autre société) et
    l'endpoint ``pnl``.

Le sélecteur lit les apps ``ventes``/``stock`` sans importer leurs modèles
(``apps.get_model`` + ``apps.stock.selectors``) — import-linter safe.

Run :
    python manage.py test apps.installations.tests_fg295_pnl -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Devis, LigneDevis, Facture
from apps.stock.models import (
    Produit, Fournisseur, FactureFournisseur,
)
from apps.installations.models import (
    Projet, ProjetChantier, ProjetDevis, BudgetProjet, BudgetEngagement,
    Installation,
)
from apps.installations.selectors import projet_pnl

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg295-co-{n}', defaults={'nom': nom or f'FG295 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'fg295-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Ferme', prenom='Client',
        email=f'fg295-{company.id}-{n}@example.invalid')


def make_projet(company, reference=None):
    n = next(_seq)
    return Projet.objects.create(
        company=company, reference=reference or f'PRG-P-{n}',
        nom='Ferme 4 forages', client=make_client(company))


def make_produit(company, prix_achat='100', prix_vente='150'):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=f'Panneau {n}', sku=f'SKU-{company.id}-{n}',
        prix_achat=Decimal(prix_achat), prix_vente=Decimal(prix_vente),
        quantite_stock=100)


def attach_devis(company, projet):
    """Devis HT 1000 rattaché au programme — support des factures client."""
    n = next(_seq)
    devis = Devis.objects.create(
        company=company, reference=f'DEV-P-{company.id}-{n}',
        client=projet.client, taux_tva=Decimal('20'))
    produit = make_produit(company)
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation='Kit',
        quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
    ProjetDevis.objects.create(company=company, projet=projet, devis=devis)
    return devis


def make_facture_client(company, devis, montant_ht, statut='emise'):
    """Facture CLIENT (revenu) rattachée à un devis. Montants figés pour un
    revenu déterministe (HT + TVA 20 % → TTC)."""
    n = next(_seq)
    ht = Decimal(str(montant_ht))
    tva = ht * Decimal('0.2')
    return Facture.objects.create(
        company=company, reference=f'FAC-{company.id}-{n}',
        client=devis.client, devis=devis, statut=statut,
        montant_ht=ht, montant_tva=tva, montant_ttc=ht + tva)


def make_facture_fournisseur(company, montant_ht):
    n = next(_seq)
    four = Fournisseur.objects.create(company=company, nom=f'FourF {n}')
    return FactureFournisseur.objects.create(
        company=company, reference=f'FF-{company.id}-{n}', fournisseur=four,
        montant_ht=Decimal(str(montant_ht)),
        montant_ttc=Decimal(str(montant_ht)) * Decimal('1.2'))


def attach_chantier(company, projet, labour_jours_reels):
    n = next(_seq)
    inst = Installation.objects.create(
        company=company, reference=f'CH-{company.id}-{n}',
        client=projet.client,
        labour_jours_reels=Decimal(str(labour_jours_reels)))
    ProjetChantier.objects.create(
        company=company, projet=projet, installation=inst)
    return inst


def attach_cout_fournisseur(company, budget, montant_ht, categorie='materiel'):
    facture = make_facture_fournisseur(company, montant_ht)
    BudgetEngagement.objects.create(
        company=company, budget=budget,
        source=BudgetEngagement.Source.FACTURE,
        categorie=categorie, facture=facture)
    return facture


# ── Revenu (factures client) ──────────────────────────────────────────────────

class TestFG295Revenu(TestCase):
    def setUp(self):
        self.company = make_company()
        self.projet = make_projet(self.company)

    def test_revenu_from_client_factures(self):
        """FG295 — le revenu = Σ factures client des devis du programme (HT/TTC)."""
        devis = attach_devis(self.company, self.projet)
        make_facture_client(self.company, devis, '1000')
        make_facture_client(self.company, devis, '500')
        res = projet_pnl(self.projet)
        self.assertEqual(res['revenu']['ht'], 1500.0)
        # TTC = 1500 × 1.20 = 1800
        self.assertEqual(res['revenu']['ttc'], 1800.0)

    def test_cancelled_facture_excluded(self):
        """FG295 — une facture ANNULÉE n'est pas un revenu (exclue)."""
        devis = attach_devis(self.company, self.projet)
        make_facture_client(self.company, devis, '1000')
        make_facture_client(self.company, devis, '700', statut='annulee')
        res = projet_pnl(self.projet)
        self.assertEqual(res['revenu']['ht'], 1000.0)

    def test_no_devis_no_revenu(self):
        """FG295 — programme sans devis → revenu 0 (dégradation propre)."""
        res = projet_pnl(self.projet)
        self.assertEqual(res['revenu']['ht'], 0.0)
        self.assertEqual(res['revenu']['ttc'], 0.0)


# ── Coûts + marge consolidée ──────────────────────────────────────────────────

class TestFG295Marge(TestCase):
    def setUp(self):
        self.company = make_company()
        self.projet = make_projet(self.company)
        self.devis = attach_devis(self.company, self.projet)

    def test_marge_brute_revenu_moins_couts(self):
        """FG295 — marge brute = revenu HT − Σ coûts (matériel + sous-traitance
        + imports + main-d'œuvre)."""
        make_facture_client(self.company, self.devis, '10000')  # revenu 10000
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet,
            tarif_jour_mo=Decimal('500'))
        attach_cout_fournisseur(self.company, budget, '3000', 'materiel')
        attach_cout_fournisseur(self.company, budget, '1500', 'sous_traitance')
        attach_cout_fournisseur(self.company, budget, '500', 'divers')  # imports
        attach_chantier(self.company, self.projet, labour_jours_reels='4')  # 2000
        res = projet_pnl(self.projet)
        # coûts = 3000 + 1500 + 500 + (4 × 500) = 7000
        self.assertEqual(res['couts']['materiel'], 3000.0)
        self.assertEqual(res['couts']['sous_traitance'], 1500.0)
        self.assertEqual(res['couts']['divers'], 500.0)
        self.assertEqual(res['couts']['main_oeuvre'], 2000.0)
        self.assertEqual(res['couts']['total'], 7000.0)
        # marge = 10000 − 7000 = 3000
        self.assertEqual(res['marge_brute'], 3000.0)

    def test_marge_pct(self):
        """FG295 — marge % = marge brute / revenu HT × 100."""
        make_facture_client(self.company, self.devis, '10000')
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet)
        attach_cout_fournisseur(self.company, budget, '6000', 'materiel')
        res = projet_pnl(self.projet)
        # marge 4000 / 10000 = 40 %
        self.assertEqual(res['marge_brute'], 4000.0)
        self.assertEqual(res['marge_pct'], 40.0)

    def test_negative_marge(self):
        """FG295 — coûts > revenu → marge brute NÉGATIVE (chantier déficitaire)."""
        make_facture_client(self.company, self.devis, '1000')
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet)
        attach_cout_fournisseur(self.company, budget, '1500', 'materiel')
        res = projet_pnl(self.projet)
        self.assertEqual(res['marge_brute'], -500.0)

    def test_no_revenu_marge_pct_zero(self):
        """FG295 — revenu nul → marge % = 0 (jamais de division par zéro)."""
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet)
        attach_cout_fournisseur(self.company, budget, '800', 'materiel')
        res = projet_pnl(self.projet)
        self.assertEqual(res['revenu']['ht'], 0.0)
        self.assertEqual(res['marge_pct'], 0.0)
        self.assertEqual(res['marge_brute'], -800.0)

    def test_no_budget_costs_degrade_to_labour_only(self):
        """FG295 — sans budget rattaché, le coût fournisseur dégrade à 0 ; seule
        la main-d'œuvre (tarif 0 → 0) est comptée."""
        make_facture_client(self.company, self.devis, '5000')
        attach_chantier(self.company, self.projet, labour_jours_reels='3')
        res = projet_pnl(self.projet)
        self.assertEqual(res['couts']['total'], 0.0)
        self.assertEqual(res['main_oeuvre_jours_reels'], 3.0)
        self.assertEqual(res['marge_brute'], 5000.0)


# ── Scope société ─────────────────────────────────────────────────────────────

class TestFG295Tenant(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.projet = make_projet(self.company)
        self.devis = attach_devis(self.company, self.projet)

    def test_other_company_facture_not_counted(self):
        """FG295 — une facture d'une AUTRE société (même devis_id improbable)
        n'entre jamais dans le revenu : le revenu est scopé société."""
        make_facture_client(self.company, self.devis, '1000')
        # Société B : son propre programme + devis + facture, jamais comptés ici.
        company_b = make_company()
        projet_b = make_projet(company_b)
        devis_b = attach_devis(company_b, projet_b)
        make_facture_client(company_b, devis_b, '9999')
        res = projet_pnl(self.projet)
        self.assertEqual(res['revenu']['ht'], 1000.0)

    def test_pnl_endpoint(self):
        """FG295 — l'endpoint pnl renvoie revenu, coûts et marge."""
        make_facture_client(self.company, self.devis, '2000')
        budget = BudgetProjet.objects.create(
            company=self.company, projet=self.projet)
        attach_cout_fournisseur(self.company, budget, '800', 'materiel')
        r = self.api.get(f'{BASE}/programmes/{self.projet.id}/pnl/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['revenu']['ht'], 2000.0)
        self.assertEqual(r.data['couts']['total'], 800.0)
        self.assertEqual(r.data['marge_brute'], 1200.0)

    def test_pnl_other_company_404(self):
        """FG295 — le P&L d'un programme d'une autre société est inaccessible."""
        company_b = make_company()
        user_b = make_user(company_b)
        r = auth(user_b).get(f'{BASE}/programmes/{self.projet.id}/pnl/')
        self.assertEqual(r.status_code, 404)

    def test_pnl_requires_responsable(self):
        """FG295 — le P&L expose des coûts d'achat : réservé responsable/admin."""
        viewer = make_user(self.company, role='commercial')
        r = auth(viewer).get(f'{BASE}/programmes/{self.projet.id}/pnl/')
        self.assertEqual(r.status_code, 403)
