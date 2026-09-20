"""CAL157 — m³/jour PAR MOIS depuis l'irradiance PVGIS RÉELLE du site.

Ce qui est prouvé ici :

* une ville RECONNUE (PVGIS) rend 12 volumes mensuels pondérés, avec la
  source PVGIS citée (``pvgis_ville:<ancrage>``) ;
* le m³/jour PLAT historique (débit × heures) reste PUBLIÉ à côté, JAMAIS
  remplacé en silence, et l'écart mois par mois est calculé ;
* un site SANS coordonnées ni ville reconnue rend ``m3_mois_pvgis`` et
  ``source_irradiation`` à ``None`` — le plat reste néanmoins publié, avec
  un avertissement explicite (jamais un résultat vide) ;
* une pompe SANS courbe (débit inconnu) ne publie AUCUN volume, ni plat ni
  pondéré — la garde de ``pumping_cycle_yield`` (CLAUDE.md) tient à travers
  ce module.

Run :
    python manage.py test apps.calepinage.tests.test_pompage_mensuel -v2
"""
import unittest

from apps.calepinage.services.pompage import pompage_mensuel_pvgis


class PompageMensuelPvgisTest(unittest.TestCase):
    def test_ville_reconnue_rend_douze_volumes_pondes_et_la_source(self):
        resultat = pompage_mensuel_pvgis(
            debit_hmt_m3h=10, pumping_hours=6, ville='Casablanca')
        self.assertIsNotNone(resultat['source_irradiation'])
        self.assertTrue(resultat['source_irradiation'].startswith('pvgis'))
        self.assertEqual(len(resultat['m3_mois_pvgis']), 12)
        self.assertEqual(len(resultat['m3_mois_plat']), 12)
        self.assertEqual(len(resultat['ecart_m3_mois']), 12)

    def test_plat_jamais_remplace_en_silence(self):
        resultat = pompage_mensuel_pvgis(
            debit_hmt_m3h=10, pumping_hours=6, ville='Casablanca')
        # Le plat est le calcul EXISTANT (débit × heures × jours du mois) —
        # il ne doit dépendre d'AUCUNE irradiation.
        self.assertEqual(resultat['m3_jour_plat'], 60.0)
        self.assertEqual(resultat['m3_mois_plat'][0], 60.0 * 31)

    def test_site_sans_irradiation_connue_rend_pvgis_none(self):
        resultat = pompage_mensuel_pvgis(
            debit_hmt_m3h=10, pumping_hours=6, ville=None, lat=None, lon=None)
        self.assertIsNone(resultat['m3_mois_pvgis'])
        self.assertIsNone(resultat['source_irradiation'])
        self.assertIsNone(resultat['ecart_m3_mois'])
        # Le plat reste publié, jamais un résultat vide.
        self.assertIsNotNone(resultat['m3_mois_plat'])
        self.assertTrue(any('PVGIS' in w for w in resultat['warnings']))

    def test_pompe_sans_courbe_aucun_volume_ni_plat_ni_pondere(self):
        resultat = pompage_mensuel_pvgis(
            debit_hmt_m3h=None, pumping_hours=6, ville='Casablanca')
        self.assertIsNone(resultat['m3_jour_plat'])
        self.assertIsNone(resultat['m3_mois_plat'])
        self.assertIsNone(resultat['m3_mois_pvgis'])
        self.assertTrue(resultat['warnings'])
