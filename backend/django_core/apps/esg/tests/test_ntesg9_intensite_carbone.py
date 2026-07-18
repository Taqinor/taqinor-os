"""NTESG9 — Intensité carbone normalisée (par MAD de CA, par kWc installé,
par ETP).

Critère d'acceptation : les trois ratios se calculent indépendamment ;
l'absence d'un seul dénominateur n'empêche pas les deux autres ; jamais une
division par zéro affichée comme 0 (source dégradée → ``disponible=False``).
"""
from datetime import date
from unittest import mock

from django.test import TestCase

from testkit.factories import CompanyFactory

from apps.esg.models import PeriodeReportingESG
from apps.esg.selectors import intensite_carbone


class IntensiteCarboneTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def _periode(self):
        return PeriodeReportingESG.objects.create(
            company=self.company, libelle='T1 2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 3, 31))

    def test_no_bilan_carbone_selector_omits_every_ratio(self):
        """Aucun sélecteur qhse pour BilanCarbone au moment de ce lane : le
        numérateur (tCO2e) est toujours indisponible → les trois ratios sont
        omis avec une raison, jamais un 0."""
        periode = self._periode()
        data = intensite_carbone(periode)
        self.assertFalse(data['numerateur']['disponible'])
        self.assertIsNone(data['numerateur']['total_tco2e'])
        for ratio in data['ratios'].values():
            self.assertFalse(ratio['disponible'])
            self.assertIsNone(ratio['valeur'])
            self.assertIsNotNone(ratio['raison'])

    def test_ratios_computed_independently_when_numerateur_available(self):
        """Avec un numérateur simulé disponible : le ratio CA se calcule
        même si kWc (toujours indisponible) et ETP (aucun employé) restent
        omis — l'absence d'un dénominateur n'empêche pas les autres."""
        periode = self._periode()
        with mock.patch(
                'apps.esg.selectors._source_bilan_carbone',
                return_value={'disponible': True, 'total_tco2e': 100.0}), \
            mock.patch(
                'apps.esg.selectors._source_ca_periode',
                return_value={'disponible': True, 'total_ht': 50000.0}):
            data = intensite_carbone(periode)

        self.assertTrue(data['numerateur']['disponible'])
        self.assertEqual(data['numerateur']['total_tco2e'], 100.0)

        ca = data['ratios']['par_mad_ca']
        self.assertTrue(ca['disponible'])
        self.assertAlmostEqual(ca['valeur'], 100.0 / 50000.0)

        # kWc reste indisponible (aucun sélecteur exposé) — n'empêche pas CA.
        kwc = data['ratios']['par_kwc_installe']
        self.assertFalse(kwc['disponible'])
        self.assertIsNone(kwc['valeur'])

        # ETP indisponible (aucun employé actif) — n'empêche pas CA.
        etp = data['ratios']['par_etp']
        self.assertFalse(etp['disponible'])
        self.assertIsNone(etp['valeur'])

    def test_etp_ratio_available_with_real_effectif(self):
        from apps.rh.models import DossierEmploye

        DossierEmploye.objects.create(
            company=self.company, matricule='M1', nom='Alami',
            statut=DossierEmploye.Statut.ACTIF)
        periode = self._periode()
        with mock.patch(
                'apps.esg.selectors._source_bilan_carbone',
                return_value={'disponible': True, 'total_tco2e': 10.0}):
            data = intensite_carbone(periode)
        etp = data['ratios']['par_etp']
        self.assertTrue(etp['disponible'])
        self.assertEqual(etp['valeur'], 10.0)

    def test_ca_source_degrades_gracefully_on_exception(self):
        periode = self._periode()
        with mock.patch(
                'apps.esg.selectors._source_bilan_carbone',
                return_value={'disponible': True, 'total_tco2e': 10.0}), \
            mock.patch(
                'apps.ventes.selectors.analyse_facturation',
                side_effect=RuntimeError('boom')):
            data = intensite_carbone(periode)
        ca = data['ratios']['par_mad_ca']
        self.assertFalse(ca['disponible'])
        self.assertIsNone(ca['valeur'])

    def test_zero_denominateur_never_shown_as_zero(self):
        """Un CA agrégé nul (aucune facture) doit être ``disponible=False``,
        jamais un ratio de 0."""
        periode = self._periode()
        with mock.patch(
                'apps.esg.selectors._source_bilan_carbone',
                return_value={'disponible': True, 'total_tco2e': 10.0}), \
            mock.patch(
                'apps.ventes.selectors.analyse_facturation',
                return_value=[]):
            data = intensite_carbone(periode)
        ca = data['ratios']['par_mad_ca']
        self.assertFalse(ca['disponible'])
        self.assertIsNone(ca['valeur'])
