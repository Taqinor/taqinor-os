"""CAL198 — kits de pose : structures/fixations du catalogue ET cotes réelles
du module.

Ce qui est prouvé ici :

* sans produit module précisé, le kit garde ses cotes HISTORIQUES (celles
  du catalogue du module, section ``presets.kits`` — SOLMVP15) inchangées ;
* avec un produit module dont la fiche technique porte les trois cotes
  requises, le kit RETIENT celles du produit (``source: 'produit'``) ;
* un module SANS dimensions de pose (fiche vide, ou aucune fiche) REFUSE
  le kit, en NOMMANT le champ manquant — jamais un repli sur un autre
  module ;
* un kit inconnu, ou une société absente, refuse en nommant le champ ;
* un produit module ARCHIVÉ est signalé (``produit_module_archive``), le
  kit reste construit.

Run :
    python manage.py test apps.calepinage.tests.test_cal198_kits -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.calepinage.services.kits import (
    KitDePoseRefuse, construire_kit_de_pose,
)
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.stock.models import FicheTechnique, Produit
from authentication.models import Company


class ConstruireKitDeSposeTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Kits Co',
                                              slug='kits-co-198')
        self.kit_id = 12
        self._poser_kit()

    def _poser_kit(self, **remplace):
        """Le kit du catalogue DU MODULE (aucune table, aucune migration)."""
        ligne = {
            'id': self.kit_id,
            'code': 'VILLA-720-EW',
            'libelle': 'Chevron dos-à-dos 720 Wc',
            'modules_par_kit': 2,
            'pas_rangee_m': 1.134,
            'longueur_pente_m': 1.303,
            'puissance_module_w': 720,
            'actif': True,
        }
        ligne.update(remplace)
        enregistrer_parametres(self.company, {'presets': {'kits': [ligne]}})
        return ligne

    def _module(self, *, nom='Module', longueur_mm=None, largeur_mm=None,
                pmax_wc=None, archive=False):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'CAL198-{nom}',
            prix_achat=Decimal('900'), prix_vente=Decimal('1400'),
            quantite_stock=5, is_archived=archive)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche='module',
            longueur_mm=longueur_mm, largeur_mm=largeur_mm, pmax_wc=pmax_wc)
        return produit

    def test_sans_produit_module_cotes_historiques_du_kit(self):
        resultat = construire_kit_de_pose(self.company,
                                          kit_id=self.kit_id)
        self.assertEqual(resultat['module']['source'], 'kit')
        self.assertEqual(resultat['module']['puissance_wc'], 720)
        self.assertIsNone(resultat['produit_module_id'])
        self.assertFalse(resultat['produit_module_archive'])

    def test_avec_produit_module_complet_cotes_du_produit(self):
        module = self._module(nom='Longi 610', longueur_mm=2384,
                              largeur_mm=1303, pmax_wc=Decimal('610'))
        resultat = construire_kit_de_pose(
            self.company, kit_id=self.kit_id, produit_module_id=module.pk)
        self.assertEqual(resultat['module']['source'], 'produit')
        self.assertEqual(resultat['module']['longueur_mm'], 2384)
        self.assertEqual(resultat['module']['largeur_mm'], 1303)
        self.assertEqual(float(resultat['module']['puissance_wc']), 610.0)

    def test_module_sans_dimensions_refuse_en_nommant_le_champ(self):
        module = self._module(nom='Sans fiche complète')  # tout None
        with self.assertRaises(KitDePoseRefuse) as ctx:
            construire_kit_de_pose(
                self.company, kit_id=self.kit_id, produit_module_id=module.pk)
        self.assertIn(ctx.exception.champ,
                      ('longueur_mm', 'largeur_mm', 'puissance_wc'))

    def test_produit_module_introuvable_refuse(self):
        with self.assertRaises(KitDePoseRefuse) as ctx:
            construire_kit_de_pose(
                self.company, kit_id=self.kit_id,
                produit_module_id=999999)
        self.assertEqual(ctx.exception.champ, 'produit_module')

    def test_kit_introuvable_refuse(self):
        with self.assertRaises(KitDePoseRefuse) as ctx:
            construire_kit_de_pose(self.company, kit_id=999999)
        self.assertEqual(ctx.exception.champ, 'kit')

    def test_societe_absente_refuse(self):
        with self.assertRaises(KitDePoseRefuse) as ctx:
            construire_kit_de_pose(None, kit_id=self.kit_id)
        self.assertEqual(ctx.exception.champ, 'kit')

    def test_produit_module_archive_signale_mais_kit_construit(self):
        module = self._module(nom='Archivé', longueur_mm=2384,
                              largeur_mm=1303, pmax_wc=Decimal('610'),
                              archive=True)
        resultat = construire_kit_de_pose(
            self.company, kit_id=self.kit_id, produit_module_id=module.pk)
        self.assertTrue(resultat['produit_module_archive'])
        self.assertEqual(resultat['module']['source'], 'produit')

    def test_kit_archive_dans_le_catalogue_signale(self):
        # Le produit qui porte le PRIX du kit, lui, archivé — signalé sur
        # `kit['produit_archive']`, jamais tu.
        produit_prix = Produit.objects.create(
            company=self.company, nom='Structure', sku='CAL198-STRUCT',
            prix_achat=Decimal('50'), prix_vente=Decimal('90'),
            quantite_stock=1, is_archived=True)
        self._poser_kit(produit_id=produit_prix.pk)
        resultat = construire_kit_de_pose(self.company,
                                          kit_id=self.kit_id)
        self.assertTrue(resultat['kit']['produit_archive'])
