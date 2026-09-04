"""AUD225 — `rotation_report` valorise avec l'accesseur de coût UNIQUE (DC28).

Défaut d'origine : l'écran dead-stock (FG57) calculait une TROISIÈME « valeur du
stock » indépendante — ``prix_achat`` catalogue brut × quantité — alors que
`stock_valuation_by_location` passe par `valuation_cost_with_source` (coût moyen
pondéré débarqué ou FIFO selon la société) et exclut la marchandise DE_TIERS.
Les deux écrans divergeaient donc structurellement pour un même produit dès
qu'une réception avait été enregistrée à un prix différent du catalogue.

INTERNE — les coûts d'achat ne sont jamais client-facing.

Run :
    python manage.py test apps.stock.test_aud225_rotation_cout_unique -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import (
    BonCommandeFournisseur, EmplacementStock, Fournisseur,
    LigneBonCommandeFournisseur, Produit, StockEmplacement,
)
from apps.stock.services import (
    ensure_emplacements, rotation_report, stock_valuation_by_location,
)


def make_company(slug='aud225-co', nom='AUD225 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestRotationCoutUnique(TestCase):
    def setUp(self):
        self.company = make_company()
        ensure_emplacements(self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur AUD225')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur AUD225', sku='AUD225-1',
            prix_achat=Decimal('1000'), prix_vente=Decimal('1800'),
            quantite_stock=100)

    def _reception(self, quantite, prix):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-AUD225-{prix}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal(str(prix)), quantite_recue=quantite)

    def _valeur_rotation(self):
        ligne = next(d for d in rotation_report(self.company)
                     if d['produit_id'] == self.produit.id)
        return Decimal(ligne['valeur_stock'])

    def _valeur_valorisation(self):
        data = stock_valuation_by_location(self.company)
        return sum((ligne['valeur'] for ligne in data['lignes']
                    if ligne['produit_id'] == self.produit.id), Decimal('0'))

    def test_meme_valeur_que_l_ecran_de_valorisation(self):
        # Réception à 1200 : le coût moyen pondéré (1200) diverge du prix
        # catalogue (1000) — c'est exactement la divergence d'origine.
        self._reception(100, '1200')

        self.assertEqual(self._valeur_rotation(), Decimal('120000.00'))
        self.assertEqual(self._valeur_rotation(), self._valeur_valorisation())

    def test_sans_reception_repli_catalogue_identique(self):
        self.assertEqual(self._valeur_rotation(), Decimal('100000.00'))
        self.assertEqual(self._valeur_rotation(), self._valeur_valorisation())

    def test_stock_de_tiers_exclu_comme_dans_la_valorisation(self):
        depot_vente = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt-vente AUD225',
            type_proprietaire=EmplacementStock.TypeProprietaire.DE_TIERS,
            ordre=800)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=depot_vente, quantite=40)

        # 100 physiques dont 40 au tiers => 60 valorisées à 1000.
        self.assertEqual(self._valeur_rotation(), Decimal('60000.00'))
        self.assertEqual(self._valeur_rotation(), self._valeur_valorisation())

    def test_quantite_physique_toujours_affichee(self):
        """Le report reste un rapport de ROTATION : la quantité affichée est la
        quantité physiquement immobilisée, tiers compris."""
        depot_vente = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt-vente AUD225',
            type_proprietaire=EmplacementStock.TypeProprietaire.DE_TIERS,
            ordre=800)
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=depot_vente, quantite=40)

        ligne = next(d for d in rotation_report(self.company)
                     if d['produit_id'] == self.produit.id)
        self.assertEqual(ligne['quantite_stock'], 100)
