"""ASTK42 (C-ASTK-008) — la « valorisation achat » du rapport T14 = l'écran
Valorisation.

Rejoue MVT-25 : un produit catalogue prix_achat 100 reçu 10 @ 50 vaut 500,00
à l'écran Valorisation (`stock_valuation_by_location`) mais le rapport T14
servait `valorisation_achat` = prix_achat × quantite_stock = 1 000,00.
Désormais T14 lit le sélecteur source unique
`apps.stock.selectors.valeur_stock_par_produit` (ASTK41) : coût de
l'accesseur unique × quantité, marchandise de tiers exclue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.reporting.tests_astk42_valorisation_t14"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, EmplacementStock, Fournisseur,
    LigneBonCommandeFournisseur, Produit, StockEmplacement,
)
from apps.stock.services import ensure_emplacements, stock_valuation_by_location
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/reports/stock/'


class ValorisationT14Tests(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='astk42-co', defaults={'nom': 'ASTK42 Co'})[0]
        self.admin = User.objects.create_user(
            username='astk42_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK42')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK42', sku='PAN-ASTK42',
            prix_vente=Decimal('200'), prix_achat=Decimal('100'),
            quantite_stock=10)
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK42',
            fournisseur=fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('50'), quantite_recue=10)

    def _t14(self):
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data

    def test_valorisation_achat_egale_ecran(self):
        ecran = stock_valuation_by_location(self.company)['total']
        self.assertEqual(ecran, Decimal('500.00'))
        self.assertEqual(self._t14()['valorisation_achat'], '500.00')

    def test_marchandise_de_tiers_exclue_comme_l_ecran(self):
        ensure_emplacements(self.company)
        depot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt-vente ASTK42',
            type_proprietaire=EmplacementStock.TypeProprietaire.DE_TIERS,
            tiers_nom='Partenaire ASTK42', ordre=800)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit, emplacement=depot,
            quantite=4)
        ecran = stock_valuation_by_location(self.company)['total']
        self.assertEqual(ecran, Decimal('300.00'))
        self.assertEqual(self._t14()['valorisation_achat'], str(ecran))

    def test_valorisation_vente_inchangee(self):
        # Hors périmètre : la valorisation VENTE reste prix_vente × stock.
        self.assertEqual(self._t14()['valorisation_vente'], '2000.00')
