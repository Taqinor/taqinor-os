"""Tests valorisation du stock par emplacement au coût moyen (N18).

Couche service (sans réseau) :
  - average_cost : moyenne pondérée des réceptions, repli prix d'achat ;
  - stock_valuation_by_location : valeur par emplacement = quantité × coût moyen.

INTERNE : les prix d'achat ne sont jamais client-facing.

Run :
    python manage.py test apps.stock.test_valuation -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    Produit, Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
    EmplacementStock,
)
from apps.stock.services import (
    average_cost, stock_valuation_by_location, transfer_stock,
    ensure_emplacements,
)

User = get_user_model()


def make_company(slug='val-co', nom='Val Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ValuationBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='val_admin', password='x', role_legacy='admin',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Grossiste')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 5kWh', sku='BAT5',
            prix_achat=Decimal('500'), prix_vente=Decimal('700'),
            quantite_stock=10)


class TestAverageCost(ValuationBase):
    def _bcf_recu(self, qte, prix):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{qte}-{prix}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=qte,
            prix_achat_unitaire=Decimal(prix), quantite_recue=qte)

    def test_fallback_to_catalog_price(self):
        self.assertEqual(average_cost(self.produit), Decimal('500'))

    def test_weighted_average(self):
        self._bcf_recu(4, '450')   # 4 × 450 = 1800
        self._bcf_recu(6, '500')   # 6 × 500 = 3000
        # (1800 + 3000) / 10 = 480.00
        self.assertEqual(average_cost(self.produit), Decimal('480.00'))


class TestValuationByLocation(ValuationBase):
    def test_valuation_splits_across_locations(self):
        ensure_emplacements(self.company)
        principal = EmplacementStock.objects.get(
            company=self.company, is_principal=True)
        camionnette = EmplacementStock.objects.get(
            company=self.company, nom='Camionnette')
        # Déplace 3 unités vers la camionnette (total inchangé = 10).
        transfer_stock(
            company=self.company, user=self.admin, produit_id=self.produit.id,
            source_id=principal.id, destination_id=camionnette.id, quantite=3)
        result = stock_valuation_by_location(self.company)
        by_name = {t['emplacement_nom']: t for t in result['par_emplacement']}
        # Coût moyen = prix catalogue 500 (aucun achat reçu).
        self.assertEqual(by_name['Dépôt principal']['quantite'], 7)
        self.assertEqual(by_name['Dépôt principal']['valeur'], Decimal('3500.00'))
        self.assertEqual(by_name['Camionnette']['quantite'], 3)
        self.assertEqual(by_name['Camionnette']['valeur'], Decimal('1500.00'))
        self.assertEqual(result['total'], Decimal('5000.00'))
