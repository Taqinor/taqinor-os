"""CAL155 — besoin en eau journalier/mensuel + réservoir + autonomie.

Ce qui est prouvé ici :

* AUCUN besoin saisi (ni journalier ni mensuel) ⇒ ``besoin_m3_mois`` et
  ``couverture_pct_mois`` valent ``None`` — jamais un taux de couverture
  publié contre un besoin supposé ;
* un besoin JOURNALIER constant produit une couverture mois par mois (le
  nombre de jours du mois pèse sur le besoin mensuel dérivé) ;
* un besoin MENSUEL explicite un mois donné PRIME sur le repli journalier
  CE mois-là seulement, les autres mois restent sur le repli ;
* l'autonomie du réservoir se calcule depuis le besoin journalier SAISI ;
  sans réservoir saisi, elle vaut ``None`` ;
* une production ``None`` un mois donné rend sa couverture ``None`` (jamais
  ``0``, qui se lirait « aucune eau produite »).

Fonction PURE : ce test n'a besoin d'AUCUNE base de données.

Run :
    python manage.py test apps.calepinage.tests.test_besoin_eau -v2
"""
import unittest

from apps.calepinage.services.pompage import couverture_besoin_eau


class CouvertureBesoinEauTest(unittest.TestCase):
    def test_aucun_besoin_saisi_aucune_couverture_publiee(self):
        resultat = couverture_besoin_eau(
            besoin_m3_jour=None, besoin_m3_mois=None,
            volume_reservoir_m3=10, production_m3_mois=[5] * 12)
        self.assertIsNone(resultat['besoin_m3_mois'])
        self.assertIsNone(resultat['couverture_pct_mois'])
        self.assertIsNone(resultat['autonomie_jours'])
        self.assertIsNone(resultat['besoin_source'])

    def test_besoin_journalier_constant_derive_le_mensuel(self):
        resultat = couverture_besoin_eau(
            besoin_m3_jour=5, production_m3_mois=[200] * 12)
        self.assertEqual(resultat['besoin_source'], 'saisie')
        # Janvier = 31 jours, février = 28 : le besoin mensuel DIFFÈRE.
        self.assertEqual(resultat['besoin_m3_mois'][0], 5 * 31)
        self.assertEqual(resultat['besoin_m3_mois'][1], 5 * 28)
        self.assertAlmostEqual(
            resultat['couverture_pct_mois'][0], 200 / (5 * 31) * 100, places=1)

    def test_besoin_mensuel_explicite_prime_un_seul_mois(self):
        mensuel = [None] * 12
        mensuel[0] = 999  # janvier : besoin exceptionnel saisi
        resultat = couverture_besoin_eau(
            besoin_m3_jour=5, besoin_m3_mois=mensuel,
            production_m3_mois=[100] * 12)
        self.assertEqual(resultat['besoin_m3_mois'][0], 999)
        # Février reste sur le repli journalier (28 jours).
        self.assertEqual(resultat['besoin_m3_mois'][1], 5 * 28)

    def test_autonomie_reservoir_depuis_besoin_journalier(self):
        resultat = couverture_besoin_eau(
            besoin_m3_jour=4, volume_reservoir_m3=12,
            production_m3_mois=[50] * 12)
        self.assertEqual(resultat['autonomie_jours'], 3.0)

    def test_sans_reservoir_autonomie_none(self):
        resultat = couverture_besoin_eau(
            besoin_m3_jour=4, volume_reservoir_m3=None,
            production_m3_mois=[50] * 12)
        self.assertIsNone(resultat['autonomie_jours'])

    def test_production_manquante_couverture_none_jamais_zero(self):
        production = [50] * 12
        production[3] = None
        resultat = couverture_besoin_eau(
            besoin_m3_jour=4, production_m3_mois=production)
        self.assertIsNone(resultat['couverture_pct_mois'][3])
        self.assertIsNotNone(resultat['couverture_pct_mois'][0])
