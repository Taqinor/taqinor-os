"""CALX277 — grille à prix unique ou à deux postes horaires (hors Maroc).

Ce qui est prouvé ici :

* société ``tranches`` non éditée ⇒ 359 kWh facturés 496,03 MAD TTC ± 0,01
  (facture réelle SRM n° 643769639 citée dans ``models_tariff.py``) — la
  facture d'aujourd'hui, inchangée ;
* ``prix_unique`` à 1,20 /kWh ⇒ 300 kWh facturés 360,00 ;
* ``deux_postes`` sans ``poste_bas`` ⇒ refus nommant ``poste_bas`` (et la
  facture est omise avec son motif, jamais un prix supposé) ;
* ``deux_postes`` complet ⇒ facture = kWh haut × poste haut + kWh bas × poste
  bas, et la répartition absente est refusée en la nommant.

Run :
    python manage.py test apps.parametres.tests_calx277_structures_tarif -v2
"""
import unittest
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.parametres import tariff


class StructureValidationPurTest(unittest.TestCase):
    def test_deux_postes_sans_poste_bas_refuse_en_le_nommant(self):
        erreurs = tariff.erreurs_structure(
            'deux_postes', '', None, '1.40', None)
        self.assertIn('poste_bas', erreurs)
        self.assertIn('poste_bas', erreurs['poste_bas'])
        self.assertNotIn('poste_haut', erreurs)

    def test_prix_unique_sans_prix_refuse(self):
        erreurs = tariff.erreurs_structure('prix_unique', '', None, None, None)
        self.assertIn('prix_unique_kwh', erreurs)

    def test_tranches_par_defaut_sans_erreur(self):
        self.assertEqual(
            tariff.erreurs_structure(None, '', None, None, None), {})
        self.assertEqual(
            tariff.erreurs_structure('tranches', 'MA', None, None, None), {})

    def test_structure_inconnue_et_pays_invalide_refuses(self):
        self.assertIn('structure_tarif', tariff.erreurs_structure(
            'forfait', '', None, None, None))
        self.assertIn('pays_tarif', tariff.erreurs_structure(
            'tranches', 'FRA', None, None, None))

    def test_prix_unique_facture(self):
        reglages = SimpleNamespace(structure_tarif='prix_unique',
                                   prix_unique_kwh='1.20')
        facture = tariff.facture_mensuelle(reglages, 300)
        self.assertEqual(facture['montant_ttc'], Decimal('360.00'))
        self.assertEqual(facture['structure'], 'prix_unique')

    def test_deux_postes_facture_avec_repartition(self):
        reglages = SimpleNamespace(structure_tarif='deux_postes',
                                   poste_haut='2.00', poste_bas='1.00')
        facture = tariff.facture_mensuelle(reglages, 300, kwh_poste_haut=100)
        self.assertEqual(facture['montant_ttc'], Decimal('400.00'))

    def test_deux_postes_sans_repartition_omis_en_la_nommant(self):
        reglages = SimpleNamespace(structure_tarif='deux_postes',
                                   poste_haut='2.00', poste_bas='1.00')
        facture = tariff.facture_mensuelle(reglages, 300)
        self.assertIsNone(facture['montant_ttc'])
        self.assertIn('kwh_poste_haut', facture['motif'])

    def test_deux_postes_sans_poste_bas_facture_omise(self):
        reglages = SimpleNamespace(structure_tarif='deux_postes',
                                   poste_haut='2.00', poste_bas=None)
        facture = tariff.facture_mensuelle(reglages, 300, kwh_poste_haut=100)
        self.assertIsNone(facture['montant_ttc'])
        self.assertIn('poste_bas', facture['motif'])


class StructureSurReglagesReelsTest(SimpleTestCase):
    """Sur un ``TariffSettings`` réel NON ENREGISTRÉ (aucune base)."""

    def test_societe_tranches_non_editee_facture_d_aujourd_hui(self):
        from apps.parametres.models_tariff import TariffSettings
        reglages = TariffSettings()
        self.assertEqual(reglages.structure_tarif, 'tranches')
        facture = tariff.facture_mensuelle(reglages, 359)
        self.assertAlmostEqual(facture['montant_ttc'], Decimal('496.03'),
                               delta=Decimal('0.01'))
        # Strictement la facture d'aujourd'hui (même fonction, même centime).
        self.assertEqual(facture['montant_ttc'],
                         tariff.monthly_bill(reglages, 359))

    def test_prix_unique_sur_reglages_reels(self):
        from apps.parametres.models_tariff import TariffSettings
        reglages = TariffSettings(structure_tarif='prix_unique',
                                  prix_unique_kwh=Decimal('1.20'))
        self.assertEqual(tariff.facture_mensuelle(reglages, 300)['montant_ttc'],
                         Decimal('360.00'))

    def test_deux_postes_sans_poste_bas_refuse_par_le_point_d_entree(self):
        from apps.parametres.models_tariff import TariffSettings
        reglages = TariffSettings(structure_tarif='deux_postes',
                                  poste_haut=Decimal('1.40'))
        self.assertIn('poste_bas', tariff.erreurs_reglages_tarif(reglages))

    def test_choix_du_modele_identiques_au_service(self):
        from apps.parametres.models_tariff import TariffSettings
        self.assertEqual(
            tuple(c for c, _ in TariffSettings.STRUCTURES_TARIF_CHOICES),
            tariff.STRUCTURES_TARIF)


class StructureOrmTest(TestCase):
    def test_deux_postes_sans_poste_bas_refuse_par_full_clean(self):
        from django.core.exceptions import ValidationError
        from authentication.models import Company
        from apps.parametres.models_tariff import TariffSettings
        company, _ = Company.objects.get_or_create(
            slug='calx277-co', defaults={'nom': 'CALX277 Co'})
        reglages = TariffSettings.get(company=company)
        reglages.structure_tarif = 'deux_postes'
        reglages.poste_haut = Decimal('1.40')
        with self.assertRaises(ValidationError) as ctx:
            reglages.full_clean()
        self.assertIn('poste_bas', ctx.exception.message_dict)
