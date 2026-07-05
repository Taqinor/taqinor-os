"""YSTCK8 — FG327 matériel consigné : exclusion explicite de la valorisation.

Couvre :
  * un lot consigné (`installations.MaterielConsigne`) n'ajoute AUCUN layer
    de valeur à `stock_valuation_by_location` (données structurellement
    disjointes — aucun FK vers Produit, aucun MouvementStock créé) ;
  * la garde explicite `stock_valuation_excludes_materiel_consigne` reste
    vraie même avec du matériel consigné de valeur (caution) élevée ;
  * aucune régression sur la valorisation du stock RÉELLEMENT possédé.

Run:
    python manage.py test \
        apps.stock.test_ystck8_consigne_exclu_valorisation -v 2
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.stock.models import Fournisseur, Produit
from apps.stock.services import (
    stock_valuation_by_location, stock_valuation_excludes_materiel_consigne,
)
from apps.installations.models_consignation import MaterielConsigne


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


class Ystck8Base(TestCase):
    def setUp(self):
        self.company = _company('ystck8-co')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YSTCK8')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau YSTCK8', sku='PAN-YSTCK8',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'),
            quantite_stock=10)


class TestExclusionValorisation(Ystck8Base):
    def test_materiel_consigne_najoute_aucune_valeur(self):
        valorisation_avant = stock_valuation_by_location(self.company)
        MaterielConsigne.objects.create(
            company=self.company, designation='Touret câble 500m',
            type_materiel=MaterielConsigne.TypeMateriel.TOURET,
            fournisseur=self.fournisseur, quantite=50,
            caution_unitaire=Decimal('9999'),  # caution volontairement élevée
            statut=MaterielConsigne.Statut.DETENU)
        valorisation_apres = stock_valuation_by_location(self.company)
        self.assertEqual(
            valorisation_avant['total'], valorisation_apres['total'])
        self.assertEqual(
            len(valorisation_avant['lignes']), len(valorisation_apres['lignes']))

    def test_garde_explicite_renvoie_vrai(self):
        MaterielConsigne.objects.create(
            company=self.company, designation='Palette',
            type_materiel=MaterielConsigne.TypeMateriel.PALETTE,
            quantite=20, caution_unitaire=Decimal('500'),
            statut=MaterielConsigne.Statut.DETENU)
        self.assertTrue(
            stock_valuation_excludes_materiel_consigne(self.company))

    def test_valorisation_du_stock_possede_inchangee(self):
        valorisation = stock_valuation_by_location(self.company)
        total_avant = valorisation['total']
        MaterielConsigne.objects.create(
            company=self.company, designation='Bouteille gaz',
            type_materiel=MaterielConsigne.TypeMateriel.BOUTEILLE,
            quantite=5, caution_unitaire=Decimal('300'),
            statut=MaterielConsigne.Statut.DETENU)
        valorisation_apres = stock_valuation_by_location(self.company)
        # Le total de la valorisation réelle reste identique — seul le
        # produit RÉELLEMENT possédé (Panneau YSTCK8) y figure.
        self.assertEqual(total_avant, valorisation_apres['total'])
        skus = {ligne['sku'] for ligne in valorisation_apres['lignes']}
        self.assertIn('PAN-YSTCK8', skus)

    def test_multi_tenant_consigne_autre_societe_sans_effet(self):
        autre = _company('ystck8-autre')
        MaterielConsigne.objects.create(
            company=autre, designation='Touret autre société',
            type_materiel=MaterielConsigne.TypeMateriel.TOURET,
            quantite=100, caution_unitaire=Decimal('9999'),
            statut=MaterielConsigne.Statut.DETENU)
        valorisation = stock_valuation_by_location(self.company)
        self.assertTrue(
            stock_valuation_excludes_materiel_consigne(self.company))
        self.assertEqual(len(valorisation['lignes']), 1)
