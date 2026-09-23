"""CALX279 — indexation annuelle SAISIE et fin de la contradiction 6 % / 0 %.

Ce qui est prouvé ici :

* société vierge ⇒ ``indexation_pour()`` rend ``None`` et la projection est
  à escalade 0, identique année par année au cashflow du moteur de devis
  d'aujourd'hui (``quote_engine.pricing.compute_cashflow_payback``,
  ``TARIFF_ESCALATION = 0.0``), avec la mention « aucune indexation saisie »
  — plus jamais les 6 %/an de ``DEFAULT_TARIFF_ESCALATION`` ;
* indexation saisie à 4 % sans source ⇒ refus nommant ``indexation_source`` ;
* avec source ⇒ l'année 10 porte le facteur ``1,04**9`` ± 1e-6.

Run :
    python manage.py test apps.parametres.tests_calx279_indexation -v2
"""
import unittest
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.parametres import tariff
from apps.ventes import solar_design as sd

SOURCE = 'Historique des tarifs publiés (jeu d’essai)'


class IndexationPurTest(unittest.TestCase):
    def test_taux_sans_source_refuse_en_nommant_indexation_source(self):
        erreurs = tariff.erreurs_indexation('4', '')
        self.assertIn('indexation_source', erreurs)
        self.assertIn('indexation_source', erreurs['indexation_source'])
        self.assertIn('indexation_source', tariff.erreurs_reglages_tarif(
            SimpleNamespace(indexation_tarif_pct_an='4',
                            indexation_source='')))

    def test_reglages_vierges_ou_sans_source_rendent_none(self):
        self.assertIsNone(tariff.indexation_depuis_reglages(
            SimpleNamespace(indexation_tarif_pct_an=None,
                            indexation_source='')))
        self.assertIsNone(tariff.indexation_depuis_reglages(
            SimpleNamespace(indexation_tarif_pct_an='4',
                            indexation_source='')))

    def test_avec_source_annee_10_porte_1_04_puissance_9(self):
        indexation = tariff.indexation_depuis_reglages(SimpleNamespace(
            indexation_tarif_pct_an='4', indexation_source=SOURCE))
        self.assertAlmostEqual(indexation['taux'], 0.04)
        res = sd.tariff_escalation_projection(
            annual_savings_year1=10000, upfront_cost=0,
            escalation_rate=indexation['taux'], degradation_rate=0.0,
            horizon_years=25, discount_rate=0.05)
        annee_10 = res['schedule'][9]
        self.assertEqual(annee_10['year'], 10)
        self.assertAlmostEqual(annee_10['escalated_tariff_factor'],
                               1.04 ** 9, delta=1e-6)
        self.assertIsNone(res['summary']['indexation_mention'])

    def test_sans_indexation_jamais_six_pour_cent(self):
        res = sd.tariff_escalation_projection(
            annual_savings_year1=10000, upfront_cost=0, horizon_years=10)
        self.assertEqual(res['summary']['escalation_rate'], 0.0)
        self.assertEqual(res['summary']['indexation_mention'],
                         'aucune indexation saisie')
        for ligne in res['schedule']:
            self.assertEqual(ligne['escalated_tariff_factor'], 1.0)
        self.assertTrue(any(h['cle'] == 'escalation_rate' and h['source']
                            for h in res['hypotheses']))


class ProjectionCommeLeMoteurDeDevisTest(SimpleTestCase):
    """La projection sans indexation = le cashflow du moteur de devis."""

    def test_escalade_nulle_identique_au_moteur_de_devis(self):
        from apps.ventes.quote_engine.pricing import (
            CASHFLOW_YEARS, PANEL_DEGRADATION, TARIFF_ESCALATION,
            compute_cashflow_payback,
        )
        self.assertEqual(TARIFF_ESCALATION, 0.0)
        investissement, economie = 80000.0, 12000.0
        moteur = compute_cashflow_payback(investissement, economie,
                                          inverter_replace_cost=None)
        res = sd.tariff_escalation_projection(
            annual_savings_year1=economie, upfront_cost=investissement,
            degradation_rate=PANEL_DEGRADATION,
            horizon_years=CASHFLOW_YEARS)
        self.assertEqual(len(res['schedule']), len(moteur['cashflow']))
        for ligne, flux in zip(res['schedule'], moteur['cashflow']):
            self.assertEqual(round(ligne['annual_savings']), flux)


class IndexationOrmTest(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='calx279-co', defaults={'nom': 'CALX279 Co'})

    def test_societe_vierge_indexation_pour_none(self):
        from apps.parametres.models_tariff import TariffSettings
        from apps.parametres.selectors import indexation_pour
        self.assertIsNone(indexation_pour(self.company))
        TariffSettings.get(company=self.company)
        self.assertIsNone(indexation_pour(self.company))

    def test_quatre_pour_cent_sans_source_refuse_par_le_modele(self):
        from decimal import Decimal
        from django.core.exceptions import ValidationError
        from apps.parametres.models_tariff import TariffSettings
        reglages = TariffSettings.get(company=self.company)
        reglages.indexation_tarif_pct_an = Decimal('4')
        with self.assertRaises(ValidationError) as ctx:
            reglages.full_clean()
        self.assertIn('indexation_source', ctx.exception.message_dict)

    def test_avec_source_indexation_pour_rend_le_taux(self):
        from decimal import Decimal
        from apps.parametres.models_tariff import TariffSettings
        from apps.parametres.selectors import indexation_pour
        reglages = TariffSettings.get(company=self.company)
        reglages.indexation_tarif_pct_an = Decimal('4')
        reglages.indexation_source = SOURCE
        reglages.full_clean()
        reglages.save()
        self.assertAlmostEqual(indexation_pour(self.company)['taux'], 0.04)
