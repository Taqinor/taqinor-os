"""ASTK44 (C-ASTK-009) — une transformation ne crée ni ne détruit de valeur.

Constat MVT-14 : `decouper_produit(source 10 → cible 10)` annonçait une valeur
transférée de 100,00 (10 @ 10) mais la cible, sans achat propre, retombait
sur son prix CATALOGUE (50) : la valorisation totale passait de 1 000,00 à
1 400,00 (+400). Désormais l'entrée de production porte `cout_unitaire`
(valeur transférée ÷ quantité produite), lu par le coût moyen comme une
couche de coût — même règle pour l'assemblage et le démontage.

Run :
    python manage.py test apps.stock.test_astk_cout_production
"""
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    MouvementStock, Produit,
)
from apps.stock.services import (
    consommer_et_produire_assemblage, decouper_produit, demonter_composite,
    stock_valuation_by_location,
)

User = get_user_model()


class CoutProductionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK44 Co', slug='astk44-co')
        self.user = User.objects.create_user(
            username='astk44-user', password='x', company=self.company,
            role_legacy='admin')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK44')
        self.source = self._produit('Touret ASTK44', 'SRC-ASTK44', '99')
        self._recu(self.source, 100, '10')
        self.cible = self._produit('Coupe ASTK44', 'CIB-ASTK44', '50')

    def _produit(self, nom, sku, prix_achat):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=sku,
            prix_vente=Decimal('500'), prix_achat=Decimal(prix_achat),
            quantite_stock=0)

    def _recu(self, produit, quantite, prix):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{produit.sku}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=produit, quantite=quantite,
            prix_achat_unitaire=Decimal(prix), quantite_recue=quantite)
        produit.quantite_stock = quantite
        produit.save(update_fields=['quantite_stock'])

    def _total(self):
        return stock_valuation_by_location(self.company)['total']

    def test_decoupe_valeur_constante(self):
        self.assertEqual(self._total(), Decimal('1000.00'))
        resultat = decouper_produit(
            company=self.company, produit_source=self.source,
            quantite_consommee=10, produit_cible=self.cible,
            quantite_produite=10, user=self.user)
        self.assertEqual(resultat['valeur_transferee'], Decimal('100.00'))
        self.assertEqual(self._total(), Decimal('1000.00'))
        entree = MouvementStock.objects.get(
            produit=self.cible,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE)
        self.assertEqual(entree.cout_unitaire, Decimal('10.0000'))
        # Relu en base : la sortie de la source ne porte aucun coût.
        sortie = MouvementStock.objects.get(
            produit=self.source,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE)
        self.assertIsNone(sortie.cout_unitaire)

    def test_decoupe_quantites_differentes(self):
        # 10 m consommés → 20 coupes : chaque coupe porte 100 / 20 = 5.
        decouper_produit(
            company=self.company, produit_source=self.source,
            quantite_consommee=10, produit_cible=self.cible,
            quantite_produite=20, user=self.user)
        entree = MouvementStock.objects.get(
            produit=self.cible,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE)
        self.assertEqual(entree.cout_unitaire, Decimal('5.0000'))
        self.assertEqual(self._total(), Decimal('1000.00'))

    def test_assemblage_puis_demontage_valeur_constante(self):
        composite = self._produit('Kit ASTK44', 'KIT-ASTK44', '900')
        kit = SimpleNamespace(id=4401)
        composants = [SimpleNamespace(produit=self.source, quantite=2)]
        consommer_et_produire_assemblage(
            company=self.company, kit=kit, composants=composants,
            produit_compose=composite, quantite_produite=5,
            reference='OA-ASTK44', user=self.user)
        entree = MouvementStock.objects.get(
            produit=composite,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE)
        # 2 × 10 consommés par kit ⇒ 20 par composite (jamais 900 catalogue).
        self.assertEqual(entree.cout_unitaire, Decimal('20.0000'))
        self.assertEqual(self._total(), Decimal('1000.00'))

        demonter_composite(
            company=self.company, kit=kit, quantite_demontee=5,
            lignes_recuperation=[SimpleNamespace(
                produit=self.source, quantite_recuperee=10)],
            produit_compose=composite, reference='OD-ASTK44', user=self.user)
        recup = MouvementStock.objects.get(
            produit=self.source, reference='OD-ASTK44',
            type_mouvement=MouvementStock.TypeMouvement.ENTREE)
        self.assertEqual(recup.cout_unitaire, Decimal('10.0000'))
        self.assertEqual(self._total(), Decimal('1000.00'))

    def test_mouvement_sans_cout_inchange(self):
        # Un mouvement historique (cout_unitaire NULL) n'est pas une couche.
        MouvementStock.objects.create(
            company=self.company, produit=self.cible,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=2, quantite_avant=0, quantite_apres=2)
        self.cible.quantite_stock = 2
        self.cible.save(update_fields=['quantite_stock'])
        # 1 000 (source) + 2 × 50 (catalogue de la cible).
        self.assertEqual(self._total(), Decimal('1100.00'))
