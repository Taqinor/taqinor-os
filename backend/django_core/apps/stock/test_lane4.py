"""Tests Lane 4 — Stock (catégories, fournisseurs, BCF).

Couvre :
  - L579 : tag de TYPE d'équipement additif (nullable) sur Categorie ;
  - L699 : compteurs lecture seule (produits liés + BCF associés) sur le
    sérialiseur Fournisseur ;
  - L723 : une ligne de BCF sans prix d'achat est commandable (BCF interne).

Run :
    python manage.py test apps.stock.test_lane4 -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    Produit, Categorie, Fournisseur, BonCommandeFournisseur,
    LigneBonCommandeFournisseur,
)

User = get_user_model()


def make_company(slug='lane4-co', nom='Lane4 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Lane4Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='lane4_admin', password='x', role_legacy='admin',
            company=self.company)
        self.resp = User.objects.create_user(
            username='lane4_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Grossiste Lane4')


# ── L579 — type_equipement additif sur Categorie ─────────────────────────────
class TestCategorieTypeEquipement(Lane4Base):
    def test_default_is_none(self):
        """Une catégorie créée sans type reste NON typée (comportement actuel)."""
        cat = Categorie.objects.create(company=self.company, nom='Onduleurs')
        self.assertIsNone(cat.type_equipement)

    def test_can_tag_categorie(self):
        cat = Categorie.objects.create(
            company=self.company, nom='Onduleurs réseau',
            type_equipement=Categorie.TypeEquipement.ONDULEUR)
        cat.refresh_from_db()
        self.assertEqual(cat.type_equipement, 'onduleur')

    def test_filter_products_by_type_regardless_of_name(self):
        """Un slot onduleur ne voit que les produits typés onduleur même si la
        société a renommé la catégorie."""
        cat_ond = Categorie.objects.create(
            company=self.company, nom='Mes convertisseurs maison',
            type_equipement=Categorie.TypeEquipement.ONDULEUR)
        cat_pan = Categorie.objects.create(
            company=self.company, nom='Modules PV',
            type_equipement=Categorie.TypeEquipement.PANNEAU)
        Produit.objects.create(
            company=self.company, nom='Onduleur X', sku='OND-X',
            prix_vente=Decimal('100'), categorie=cat_ond)
        Produit.objects.create(
            company=self.company, nom='Panneau Y', sku='PAN-Y',
            prix_vente=Decimal('100'), categorie=cat_pan)
        ond = Produit.objects.filter(
            company=self.company,
            categorie__type_equipement=Categorie.TypeEquipement.ONDULEUR)
        self.assertEqual([p.sku for p in ond], ['OND-X'])

    def test_serializer_exposes_type_equipement(self):
        cat = Categorie.objects.create(
            company=self.company, nom='Batteries',
            type_equipement=Categorie.TypeEquipement.BATTERIE)
        api = auth(self.admin)
        r = api.get(f'/api/django/stock/categories/{cat.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['type_equipement'], 'batterie')

    def test_update_type_equipement_via_api(self):
        cat = Categorie.objects.create(company=self.company, nom='Pompes')
        api = auth(self.admin)
        r = api.patch(
            f'/api/django/stock/categories/{cat.id}/',
            {'type_equipement': 'pompe'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        cat.refresh_from_db()
        self.assertEqual(cat.type_equipement, 'pompe')


# ── L578 — ProduitSerializer expose le type de catégorie (slot d'équipement) ──
class TestProduitCategorieType(Lane4Base):
    def test_produit_exposes_categorie_type_when_typed(self):
        """Le produit d'une catégorie typée remonte categorie_type +
        categorie_type_display à plat (pour le filtre de slot du chantier)."""
        cat = Categorie.objects.create(
            company=self.company, nom='Mes convertisseurs maison',
            type_equipement=Categorie.TypeEquipement.ONDULEUR)
        prod = Produit.objects.create(
            company=self.company, nom='Onduleur X', sku='OND-X',
            prix_vente=Decimal('100'), categorie=cat)
        api = auth(self.admin)
        r = api.get(f'/api/django/stock/produits/{prod.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['categorie_type'], 'onduleur')
        self.assertEqual(r.data['categorie_type_display'], 'Onduleur')

    def test_produit_categorie_type_none_when_untyped(self):
        """Catégorie non typée → categorie_type None (comportement historique :
        le picker reste sur la liste BOM complète côté frontend)."""
        cat = Categorie.objects.create(company=self.company, nom='Divers')
        prod = Produit.objects.create(
            company=self.company, nom='Vis inox', sku='VIS-1',
            prix_vente=Decimal('5'), categorie=cat)
        api = auth(self.admin)
        r = api.get(f'/api/django/stock/produits/{prod.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data['categorie_type'])
        self.assertIsNone(r.data['categorie_type_display'])

    def test_produit_categorie_type_none_when_no_categorie(self):
        """Produit sans catégorie → pas d'erreur, type None."""
        prod = Produit.objects.create(
            company=self.company, nom='Sans cat', sku='SC-1',
            prix_vente=Decimal('5'))
        api = auth(self.admin)
        r = api.get(f'/api/django/stock/produits/{prod.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data['categorie_type'])
        self.assertIsNone(r.data['categorie_type_display'])


# ── L699 — compteurs lecture seule sur la fiche fournisseur ──────────────────
class TestFournisseurCounts(Lane4Base):
    def test_counts_products_and_bcf(self):
        Produit.objects.create(
            company=self.company, nom='P1', sku='P1',
            prix_vente=Decimal('100'), fournisseur=self.fournisseur)
        Produit.objects.create(
            company=self.company, nom='P2', sku='P2',
            prix_vente=Decimal('100'), fournisseur=self.fournisseur)
        # Produit sans fournisseur — ne doit pas être compté.
        Produit.objects.create(
            company=self.company, nom='P3', sku='P3',
            prix_vente=Decimal('100'))
        BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-1',
            fournisseur=self.fournisseur)
        BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-2',
            fournisseur=self.fournisseur)
        BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-3',
            fournisseur=self.fournisseur)
        api = auth(self.resp)
        r = api.get(f'/api/django/stock/fournisseurs/{self.fournisseur.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['nb_produits'], 2)
        self.assertEqual(r.data['nb_bons_commande'], 3)

    def test_counts_zero_when_unused(self):
        autre = Fournisseur.objects.create(company=self.company, nom='Inutilisé')
        api = auth(self.resp)
        r = api.get(f'/api/django/stock/fournisseurs/{autre.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['nb_produits'], 0)
        self.assertEqual(r.data['nb_bons_commande'], 0)


# ── L723 — ligne BCF sans prix d'achat commandable (BCF interne) ─────────────
class TestBcfPrixOptionnel(Lane4Base):
    def test_create_bcf_with_zero_price_line(self):
        """Un produit sans prix de vente reste commandable : sa ligne BCF peut
        avoir un prix d'achat nul/absent (BCF interne ≠ devis)."""
        # Produit sans prix de vente (ex. pompe à prix non renseigné).
        pompe = Produit.objects.create(
            company=self.company, nom='Pompe OSP non prisée', sku='PMP-NP',
            prix_vente=Decimal('0'), quantite_stock=0)
        api = auth(self.resp)
        payload = {
            'fournisseur': self.fournisseur.id,
            'lignes': [
                {'produit': pompe.id, 'quantite': 5},
            ],
        }
        r = api.post(
            '/api/django/stock/bons-commande-fournisseur/', payload,
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        ligne = LigneBonCommandeFournisseur.objects.get(
            bon_commande_id=r.data['id'])
        self.assertEqual(ligne.prix_achat_unitaire, Decimal('0'))
        self.assertEqual(ligne.quantite, 5)
