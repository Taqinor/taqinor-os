"""AUD211 — `stock_valuation_by_location` exclut le stock DE_TIERS.

Défaut d'origine : l'écran de valorisation par emplacement (et son export
.xlsx, qui consomme la même fonction) valorisait la marchandise posée sur un
emplacement ``DE_TIERS`` (dépôt-vente : dans nos murs, propriété d'un tiers)
comme un actif de la société — alors que `valorisation_a_date` (XSTK13/NTWMS19)
l'exclut correctement depuis toujours. Les deux valorisations divergeaient donc
structurellement dès qu'un dépôt-vente existait.

INTERNE — les coûts d'achat ne sont jamais client-facing.

Run :
    python manage.py test apps.stock.test_aud211_valorisation_de_tiers -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import EmplacementStock, Produit, StockEmplacement
from apps.stock.services import (
    ensure_emplacements, quantite_de_tiers, stock_valuation_by_location,
)


def make_company(slug='aud211-co', nom='AUD211 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestValorisationExclutDeTiers(TestCase):
    def setUp(self):
        self.company = make_company()
        ensure_emplacements(self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie AUD211', sku='AUD211-1',
            prix_achat=Decimal('1000'), prix_vente=Decimal('1500'),
            quantite_stock=100)
        self.depot_vente = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt-vente Partenaire',
            type_proprietaire=EmplacementStock.TypeProprietaire.DE_TIERS,
            tiers_nom='Partenaire SARL', ordre=800)

    def _poser_de_tiers(self, quantite):
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.depot_vente, quantite=quantite)

    def test_stock_de_tiers_exclu_de_la_valorisation(self):
        self._poser_de_tiers(30)
        self.assertEqual(quantite_de_tiers(self.company, self.produit), 30)

        data = stock_valuation_by_location(self.company)

        # 100 en stock dont 30 appartenant au tiers => 70 valorisés à 1000.
        # Avant AUD211 : 100 000,00 (les 30 unités du tiers incluses).
        self.assertEqual(data['total'], Decimal('70000.00'))
        quantite_totale = sum(ligne['quantite'] for ligne in data['lignes'])
        self.assertEqual(quantite_totale, 70)

    def test_emplacement_de_tiers_absent_du_detail(self):
        self._poser_de_tiers(30)

        data = stock_valuation_by_location(self.company)

        noms_lignes = {ligne['emplacement_nom'] for ligne in data['lignes']}
        self.assertNotIn('Dépôt-vente Partenaire', noms_lignes)
        noms_totaux = {e['emplacement_nom'] for e in data['par_emplacement']}
        self.assertNotIn('Dépôt-vente Partenaire', noms_totaux)

    def test_sans_depot_de_tiers_resultat_inchange(self):
        """Cas de toutes les sociétés existantes : aucun emplacement DE_TIERS
        renseigné => valorisation strictement identique à l'historique."""
        data = stock_valuation_by_location(self.company)
        self.assertEqual(data['total'], Decimal('100000.00'))

    def test_emplacement_interne_non_principal_reste_valorise(self):
        """La garde ne doit toucher QUE le DE_TIERS : notre propre stock
        déporté (camionnette, 3PL) reste un actif."""
        camionnette = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette 1',
            type_proprietaire=EmplacementStock.TypeProprietaire.CHEZ_TIERS,
            ordre=810)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=camionnette, quantite=20)
        self._poser_de_tiers(30)

        data = stock_valuation_by_location(self.company)

        # 100 − 30 (tiers) = 70, dont 20 en camionnette.
        self.assertEqual(data['total'], Decimal('70000.00'))
        par_nom = {e['emplacement_nom']: e for e in data['par_emplacement']}
        self.assertEqual(par_nom['Camionnette 1']['quantite'], 20)
