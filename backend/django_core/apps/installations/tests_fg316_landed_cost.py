"""
FG316 — Frais d'import & coût de revient débarqué (landed cost).

Couvre :
  * création de frais et de lignes de coût débarqué via l'API, société +
    `created_by` posés CÔTÉ SERVEUR ;
  * un dossier d'une autre société est rejeté ;
  * le calcul du coût débarqué : frais répartis au prorata de la valeur FOB ;
  * cout_fob_unitaire ;
  * le scope société et la barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg316_landed_cost -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    DossierImport, FraisImport, LandedCostLigne,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg316-co-{n}', defaults={'nom': nom or f'FG316 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg316-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_dossier(company):
    n = next(_seq)
    return DossierImport.objects.create(
        company=company, reference=f'IMP-{n}', designation='Conteneur')


class TestFraisEtLignes(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.dossier = make_dossier(self.company)

    def test_create_frais_server_side(self):
        r = self.api.post(f'{BASE}/frais-import/', {
            'dossier': self.dossier.id, 'categorie': 'fret', 'montant': '20000',
        })
        self.assertEqual(r.status_code, 201, r.data)
        f = FraisImport.objects.get(id=r.data['id'])
        self.assertEqual(f.company_id, self.company.id)
        self.assertEqual(f.created_by_id, self.user.id)

    def test_create_ligne_and_fob_unitaire(self):
        r = self.api.post(f'{BASE}/landed-cost-lignes/', {
            'dossier': self.dossier.id, 'designation': 'Panneau',
            'quantite': '100', 'valeur_fob': '120000',
        })
        self.assertEqual(r.status_code, 201, r.data)
        # FOB unitaire = 120000 / 100 = 1200.
        self.assertEqual(float(r.data['cout_fob_unitaire']), 1200.0)

    def test_foreign_dossier_rejected(self):
        autre = make_company()
        d_o = make_dossier(autre)
        r = self.api.post(f'{BASE}/frais-import/', {
            'dossier': d_o.id, 'categorie': 'douane', 'montant': '1',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_ligne_requires_product_or_designation(self):
        r = self.api.post(f'{BASE}/landed-cost-lignes/', {
            'dossier': self.dossier.id, 'quantite': '1', 'valeur_fob': '1',
        })
        self.assertEqual(r.status_code, 400, r.data)


class TestLandedCostComputation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.dossier = make_dossier(self.company)
        # Deux SKU : FOB 80000 et 20000 (total 100000).
        self.l1 = LandedCostLigne.objects.create(
            company=self.company, dossier=self.dossier, designation='A',
            quantite=80, valeur_fob=80000)
        self.l2 = LandedCostLigne.objects.create(
            company=self.company, dossier=self.dossier, designation='B',
            quantite=20, valeur_fob=20000)
        # Frais totaux 10000.
        FraisImport.objects.create(
            company=self.company, dossier=self.dossier, categorie='fret',
            montant=6000)
        FraisImport.objects.create(
            company=self.company, dossier=self.dossier, categorie='douane',
            montant=4000)

    def test_landed_cost_prorata(self):
        r = self.api.get(f'{BASE}/dossiers-import/{self.dossier.id}/'
                         'landed-cost/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['total_fob'], 100000.0)
        self.assertEqual(r.data['total_frais'], 10000.0)
        self.assertEqual(r.data['total_landed'], 110000.0)
        by_id = {ln['ligne_id']: ln for ln in r.data['lignes']}
        # Ligne A : 80 % des frais = 8000 → débarqué 88000 ; unitaire 1100.
        a = by_id[self.l1.id]
        self.assertEqual(a['quote_part_frais'], 8000.0)
        self.assertEqual(a['cout_debarque_total'], 88000.0)
        self.assertEqual(a['cout_debarque_unitaire'], 1100.0)
        # Ligne B : 20 % des frais = 2000 → débarqué 22000 ; unitaire 1100.
        b = by_id[self.l2.id]
        self.assertEqual(b['quote_part_frais'], 2000.0)
        self.assertEqual(b['cout_debarque_total'], 22000.0)

    def test_no_fob_no_crash(self):
        dossier = make_dossier(self.company)
        FraisImport.objects.create(
            company=self.company, dossier=dossier, categorie='fret',
            montant=5000)
        r = self.api.get(f'{BASE}/dossiers-import/{dossier.id}/landed-cost/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['total_fob'], 0.0)
        self.assertEqual(r.data['lignes'], [])


class TestScopeRole(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.dossier = make_dossier(self.company)

    def test_write_requires_role(self):
        normal = make_user(self.company, role='normal')
        api = auth(normal)
        r = api.post(f'{BASE}/frais-import/', {
            'dossier': self.dossier.id, 'categorie': 'fret', 'montant': '1',
        })
        self.assertEqual(r.status_code, 403, r.data)

    def test_scope_isolation(self):
        other = make_company()
        d_o = make_dossier(other)
        FraisImport.objects.create(
            company=other, dossier=d_o, categorie='fret', montant=1)
        FraisImport.objects.create(
            company=self.company, dossier=self.dossier, categorie='fret',
            montant=1)
        r = self.api.get(f'{BASE}/frais-import/')
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)


# ── DC38 — Le coût débarqué (FG316) se replie dans le coût moyen pondéré ──────
#          stock via `frais_annexes` (FG67), pas de champ de coût parallèle. ──

class TestDC38LandedCostVersCoutStock(TestCase):
    def setUp(self):
        from apps.stock.models import (
            Produit, Fournisseur, BonCommandeFournisseur,
            LigneBonCommandeFournisseur,
        )
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W',
            prix_vente=0, prix_achat=0, quantite_stock=0, seuil_alerte=0)
        self.fournisseur = Fournisseur.objects.get_or_create(
            company=self.company, nom='Import Co')[0]
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-DC38-{next(_seq)}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            created_by=self.user)
        self.ligne_bcf = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.produit,
            quantite=10, prix_achat_unitaire=100, quantite_recue=10)
        self.dossier = DossierImport.objects.create(
            company=self.company, reference=f'IMP-DC38-{next(_seq)}',
            designation='Conteneur panneaux', bon_commande=self.bcf)
        LandedCostLigne.objects.create(
            company=self.company, dossier=self.dossier, produit=self.produit,
            designation='Panneau 550W', quantite=10, valeur_fob=10000)
        FraisImport.objects.create(
            company=self.company, dossier=self.dossier, categorie='fret',
            montant=2000)

    def test_appliquer_reporte_frais_annexes_et_cout_moyen(self):
        from decimal import Decimal
        from apps.stock.services import average_cost_with_source
        r = self.api.post(
            f'{BASE}/dossiers-import/{self.dossier.id}/appliquer-cout-stock/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['lignes_maj'], 1)
        self.ligne_bcf.refresh_from_db()
        # Seule ligne → 100 % des 2000 de frais.
        self.assertEqual(self.ligne_bcf.frais_annexes, Decimal('2000.00'))
        # Coût moyen = prix_achat_unitaire + frais/quantité = 100 + 200 = 300.
        cout, source = average_cost_with_source(self.produit)
        self.assertEqual(source, 'achats')
        self.assertEqual(cout, Decimal('300.00'))

    def test_appliquer_sans_bon_commande_rejete(self):
        dossier = make_dossier(self.company)  # pas de bon_commande
        r = self.api.post(
            f'{BASE}/dossiers-import/{dossier.id}/appliquer-cout-stock/')
        self.assertEqual(r.status_code, 400, r.data)

    def test_appliquer_reserve_aux_roles(self):
        normal = make_user(self.company, role='normal')
        r = auth(normal).post(
            f'{BASE}/dossiers-import/{self.dossier.id}/appliquer-cout-stock/')
        self.assertEqual(r.status_code, 403, r.data)
