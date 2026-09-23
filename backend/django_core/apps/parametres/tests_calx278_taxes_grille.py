"""CALX278 — taxes séparées des prix dans la grille société.

Ce qui est prouvé ici :

* société non éditée ⇒ facture identique à aujourd'hui au centime (359 kWh ⇒
  496,03 MAD TTC, facture réelle citée dans ``models_tariff.py``), sans
  ventilation ;
* ``prix_incluent_taxes = False`` avec une TVA saisie à 20 % ⇒ le TTC publié
  égale HT × 1,20 ± 0,01 et la ventilation HT / taxes / TTC est servie ;
* taxe sans source ⇒ refus nommant ``taxes[0].source`` ;
* prix « hors taxes » sur le barème par défaut (qui est TTC) ⇒ refusé ;
* charge minimale : appliquée sur la période fournie, facture omise si le
  nombre de jours manque.

Run :
    python manage.py test apps.parametres.tests_calx278_taxes_grille -v2
"""
import unittest
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.parametres import tariff

TVA_20 = {'libelle': 'TVA', 'taux_pct': 20, 'assiette': 'total',
          'source': 'Code général des impôts (jeu d’essai)'}


def _grille_ht(**champs):
    base = {'structure_tarif': 'prix_unique', 'prix_unique_kwh': '1.15142',
            'prix_incluent_taxes': False, 'taxes': [TVA_20],
            'charge_minimale_mad_jour': None}
    base.update(champs)
    return SimpleNamespace(**base)


class TaxesPurTest(unittest.TestCase):
    def test_prix_ht_avec_tva_saisie_ttc_egal_ht_fois_1_20(self):
        facture = tariff.facture_mensuelle(_grille_ht(), 359)
        ventilation = facture['ventilation']
        self.assertIsNotNone(ventilation)
        self.assertEqual(ventilation['ht'], Decimal('413.36'))
        self.assertEqual(len(ventilation['taxes']), 1)
        self.assertEqual(ventilation['taxes'][0]['source'], TVA_20['source'])
        self.assertAlmostEqual(facture['montant_ttc'],
                               ventilation['ht'] * Decimal('1.20'),
                               delta=Decimal('0.01'))
        self.assertEqual(facture['montant_ttc'], ventilation['ttc'])
        self.assertFalse(facture['taxes_incluses'])

    def test_taxe_sans_source_refusee_en_nommant_taxes_0_source(self):
        sans_source = {**TVA_20, 'source': ''}
        erreurs = tariff.erreurs_taxes(False, [sans_source], None,
                                       'prix_unique', None)
        self.assertIn('taxes', erreurs)
        self.assertIn('taxes[0].source', erreurs['taxes'])

    def test_point_d_entree_unique_relaie_le_refus(self):
        erreurs = tariff.erreurs_reglages_tarif(
            _grille_ht(taxes=[{**TVA_20, 'source': None}]))
        self.assertIn('taxes[0].source', erreurs['taxes'])

    def test_hors_taxes_sur_bareme_par_defaut_refuse(self):
        erreurs = tariff.erreurs_taxes(False, [TVA_20], None, 'tranches', None)
        self.assertIn('prix_incluent_taxes', erreurs)
        # Paliers HT saisis par la société : accepté.
        self.assertEqual(tariff.erreurs_taxes(
            False, [TVA_20], None, 'tranches',
            [{'max_kwh': None, 'prix_kwh_ttc': '1.15142'}]), {})

    def test_assiette_inconnue_refusee(self):
        erreurs = tariff.erreurs_taxes(
            False, [{**TVA_20, 'assiette': 'abonnement'}], None,
            'prix_unique', None)
        self.assertIn('taxes[0].assiette', erreurs['taxes'])

    def test_charge_minimale_appliquee_sur_la_periode_fournie(self):
        grille = _grille_ht(charge_minimale_mad_jour='5.00', taxes=[])
        facture = tariff.facture_mensuelle(grille, 10, jours=30)
        # 10 kWh × 1,15142 = 11,51 HT < 30 j × 5,00 = 150,00 ⇒ 150,00.
        self.assertEqual(facture['ventilation']['ht'], Decimal('150.00'))

    def test_charge_minimale_sans_jours_facture_omise(self):
        grille = _grille_ht(charge_minimale_mad_jour='5.00')
        facture = tariff.facture_mensuelle(grille, 10)
        self.assertIsNone(facture['montant_ttc'])
        self.assertIn('jours', facture['motif'])


class TaxesSurReglagesReelsTest(SimpleTestCase):
    """Sur un ``TariffSettings`` réel NON ENREGISTRÉ (aucune base)."""

    def test_societe_non_editee_facture_identique_au_centime(self):
        from apps.parametres.models_tariff import TariffSettings
        reglages = TariffSettings()
        self.assertTrue(reglages.prix_incluent_taxes)
        facture = tariff.facture_mensuelle(reglages, 359)
        self.assertEqual(facture['montant_ttc'], Decimal('496.03'))
        self.assertEqual(facture['montant_ttc'],
                         tariff.monthly_bill(reglages, 359))
        self.assertIsNone(facture['ventilation'])
        self.assertEqual(tariff.erreurs_reglages_tarif(reglages), {})

    def test_prix_ht_tva_20_sur_reglages_reels(self):
        from apps.parametres.models_tariff import TariffSettings
        reglages = TariffSettings(
            structure_tarif='prix_unique', prix_unique_kwh=Decimal('1.15142'),
            prix_incluent_taxes=False, taxes=[TVA_20])
        self.assertEqual(tariff.erreurs_reglages_tarif(reglages), {})
        facture = tariff.facture_mensuelle(reglages, 359)
        self.assertAlmostEqual(facture['montant_ttc'], Decimal('496.03'),
                               delta=Decimal('0.01'))


class TaxesOrmTest(TestCase):
    def test_taxe_sans_source_refusee_par_full_clean(self):
        from django.core.exceptions import ValidationError
        from authentication.models import Company
        from apps.parametres.models_tariff import TariffSettings
        company, _ = Company.objects.get_or_create(
            slug='calx278-co', defaults={'nom': 'CALX278 Co'})
        reglages = TariffSettings.get(company=company)
        reglages.structure_tarif = 'prix_unique'
        reglages.prix_unique_kwh = Decimal('1.15142')
        reglages.prix_incluent_taxes = False
        reglages.taxes = [{**TVA_20, 'source': ''}]
        with self.assertRaises(ValidationError) as ctx:
            reglages.full_clean()
        self.assertIn('taxes', ctx.exception.message_dict)
        self.assertIn('taxes[0].source',
                      ' '.join(ctx.exception.message_dict['taxes']))
