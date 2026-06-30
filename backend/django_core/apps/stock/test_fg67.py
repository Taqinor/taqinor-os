"""Tests FG67 / DC38 — coût débarqué (landed cost) + méthode FIFO optionnelle.

  - frais_annexes (fret/douane/TVA import/transit) repliés dans le coût moyen
    pondéré (DC38 : pas de champ de coût parallèle) ;
  - méthode de valorisation société : 'wavg' (défaut) ou 'fifo' ;
  - fifo_cost_with_source valorise les couches d'entrée restantes (dernières
    entrées) ; wavg garde le comportement historique quand frais = 0.

INTERNE : les prix d'achat / coûts ne sont jamais client-facing.

Run :
    python manage.py test apps.stock.test_fg67 -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    Produit, Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
)
from apps.stock.services import (
    average_cost, average_cost_with_source, fifo_cost_with_source,
    valuation_cost_with_source, stock_valuation_method,
    VALUATION_WAVG, VALUATION_FIFO,
)

User = get_user_model()


def make_company(slug='fg67-co', nom='FG67 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FG67Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Importateur')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur importé', sku='IMP1',
            prix_achat=Decimal('1000'), prix_vente=Decimal('1500'),
            quantite_stock=0)

    def _bcf_recu(self, qte, prix, frais=0, ref=None):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=ref or f'BCF-{qte}-{prix}-{frais}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=qte,
            prix_achat_unitaire=Decimal(str(prix)),
            frais_annexes=Decimal(str(frais)), quantite_recue=qte)
        # Reflète le stock reçu (le service de réception fait cela en prod).
        self.produit.quantite_stock += qte
        self.produit.save(update_fields=['quantite_stock'])
        return bc


class TestLandedCost(FG67Base):
    """DC38 — frais annexes repliés dans le coût moyen pondéré."""

    def test_no_frais_keeps_historical_behaviour(self):
        self._bcf_recu(10, '1000', frais=0)
        cout, source = average_cost_with_source(self.produit)
        self.assertEqual(cout, Decimal('1000.00'))
        self.assertEqual(source, 'achats')

    def test_frais_annexes_folded_into_average(self):
        # 10 unités à 1000 + 500 de frais => coût débarqué unitaire = 1050.
        self._bcf_recu(10, '1000', frais=500)
        self.assertEqual(average_cost(self.produit), Decimal('1050.00'))

    def test_cout_unitaire_debarque_property(self):
        bc = self._bcf_recu(4, '1000', frais=400)
        ligne = bc.lignes.first()
        # 1000 + 400/4 = 1100.
        self.assertEqual(ligne.cout_unitaire_debarque, Decimal('1100'))

    def test_cout_unitaire_debarque_zero_frais(self):
        bc = self._bcf_recu(4, '1000', frais=0)
        self.assertEqual(
            bc.lignes.first().cout_unitaire_debarque, Decimal('1000'))


class TestValuationMethod(FG67Base):
    """FG67 — méthode société : wavg (défaut) vs fifo."""

    def test_default_method_is_wavg(self):
        self.assertEqual(stock_valuation_method(self.company), VALUATION_WAVG)

    def test_default_method_none_company(self):
        self.assertEqual(stock_valuation_method(None), VALUATION_WAVG)

    def test_valuation_dispatches_to_wavg_by_default(self):
        self._bcf_recu(4, '900', frais=0, ref='A')
        self._bcf_recu(6, '1100', frais=0, ref='B')
        # wavg = (4*900 + 6*1100)/10 = 1020.
        cout, _ = valuation_cost_with_source(self.produit)
        self.assertEqual(cout, Decimal('1020.00'))

    def test_fifo_values_latest_layers(self):
        # Entrées : 4 @ 900 (ancien) puis 6 @ 1100 (récent). Stock = 10.
        self._bcf_recu(4, '900', frais=0, ref='OLD')
        self._bcf_recu(6, '1100', frais=0, ref='NEW')
        # On consomme 0 ; FIFO conserve les 10 unités => couches récentes
        # d'abord : 6 @ 1100 + 4 @ 900 = (6600 + 3600)/10 = 1020.
        cout, source = fifo_cost_with_source(self.produit)
        self.assertEqual(source, 'achats')
        self.assertEqual(cout, Decimal('1020.00'))

    def test_fifo_partial_stock_keeps_recent_layers(self):
        self._bcf_recu(4, '900', frais=0, ref='OLD')
        self._bcf_recu(6, '1100', frais=0, ref='NEW')
        # Simule une consommation : il ne reste que 6 unités (les plus
        # récentes en FIFO valorisation = couches récentes restantes).
        self.produit.quantite_stock = 6
        self.produit.save(update_fields=['quantite_stock'])
        cout, _ = fifo_cost_with_source(self.produit)
        # 6 unités valorisées à la couche la plus récente (1100).
        self.assertEqual(cout, Decimal('1100.00'))

    def test_fifo_fallback_catalogue_without_receipts(self):
        cout, source = fifo_cost_with_source(self.produit)
        self.assertEqual(source, 'catalogue')
        self.assertEqual(cout, Decimal('1000'))

    def test_explicit_method_param_overrides(self):
        self._bcf_recu(4, '900', frais=0, ref='OLD')
        self._bcf_recu(6, '1100', frais=0, ref='NEW')
        self.produit.quantite_stock = 6
        self.produit.save(update_fields=['quantite_stock'])
        wavg, _ = valuation_cost_with_source(
            self.produit, method=VALUATION_WAVG)
        fifo, _ = valuation_cost_with_source(
            self.produit, method=VALUATION_FIFO)
        # wavg ignore le stock restant (moyenne sur tout le reçu) = 1020 ;
        # fifo valorise les 6 unités récentes = 1100.
        self.assertEqual(wavg, Decimal('1020.00'))
        self.assertEqual(fifo, Decimal('1100.00'))
