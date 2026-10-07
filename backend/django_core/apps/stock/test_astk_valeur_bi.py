"""ASTK41 (C-ASTK-008) — la valeur BI du stock = la valeur de l'écran Valorisation.

Constat MVT-25 : un produit au catalogue prix_achat 100 reçu 10 @ 50 valait
500,00 à l'écran Valorisation mais 1 000,00 dans le jeu BI `stock_produits`
(`valeur_achat = prix_achat × quantite_stock`). Désormais le jeu BI lit le
sélecteur source unique `valeur_stock_par_produit(company)` (coût de
l'accesseur unique × quantité, marchandise de tiers exclue comme l'écran).

Run :
    python manage.py test apps.stock.test_astk_valeur_bi
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.bi_datasets import PRODUITS_DATASET
from apps.stock.models import (
    BonCommandeFournisseur, EmplacementStock, Fournisseur,
    LigneBonCommandeFournisseur, Produit, StockEmplacement,
)
from apps.stock.selectors import valeur_stock_par_produit
from apps.stock.services import ensure_emplacements, stock_valuation_by_location
from authentication.models import Company
from core import data_explorer

User = get_user_model()


class ValeurBiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK41 Co', slug='astk41-co')
        self.admin = User.objects.create_superuser(
            username='astk41_admin', password='x', email='astk41@x.ma')
        self.admin.company = self.company
        self.admin.save(update_fields=['company'])
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK41')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK41', sku='PAN-ASTK41',
            prix_vente=Decimal('200'), prix_achat=Decimal('100'),
            quantite_stock=10)
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK41',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('50'), quantite_recue=10)

    def _valeur_bi(self):
        lignes = data_explorer.run_query(
            PRODUITS_DATASET, self.company, self.admin,
            {'select': ['id', 'valeur_achat']})
        return {r['id']: r['valeur_achat'] for r in lignes}[self.produit.id]

    def test_valeur_bi_egale_ecran(self):
        ecran = stock_valuation_by_location(self.company)['total']
        self.assertEqual(ecran, Decimal('500.00'))
        self.assertEqual(self._valeur_bi(), Decimal('500.00'))
        self.assertEqual(
            valeur_stock_par_produit(self.company)[self.produit.id],
            Decimal('500.00'))

    def test_marchandise_de_tiers_exclue_comme_l_ecran(self):
        ensure_emplacements(self.company)
        depot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt-vente ASTK41',
            type_proprietaire=EmplacementStock.TypeProprietaire.DE_TIERS,
            tiers_nom='Partenaire ASTK41', ordre=800)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit, emplacement=depot,
            quantite=4)
        ecran = stock_valuation_by_location(self.company)['total']
        self.assertEqual(ecran, Decimal('300.00'))
        self.assertEqual(self._valeur_bi(), ecran)

    def test_produit_sans_stock_vaut_zero(self):
        vide = Produit.objects.create(
            company=self.company, nom='Vide ASTK41', sku='VIDE-ASTK41',
            prix_vente=Decimal('10'), prix_achat=Decimal('5'),
            quantite_stock=0)
        lignes = data_explorer.run_query(
            PRODUITS_DATASET, self.company, self.admin,
            {'select': ['id', 'valeur_achat']})
        valeurs = {r['id']: r['valeur_achat'] for r in lignes}
        self.assertEqual(valeurs[vide.id], Decimal('0.00'))
