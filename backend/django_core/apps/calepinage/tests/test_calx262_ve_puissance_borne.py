"""CALX262 — borner la recharge par la puissance de la borne, et dire le
débordement.

Ce qui est tenu :

* ``vehicule.puissance_borne_kw`` SAISIE plafonne l'énergie horaire ;
* le débordement (ce qui ne tient pas dans la fenêtre à cause de ce
  plafond) est publié à part, ``energie_non_placee_kwh``, JAMAIS masqué ;
* absente ⇒ aucun plafond, comportement d'AUJOURD'HUI (non-régression
  CAL154/CALX261) ;
* une puissance négative est REFUSÉE en nommant le champ.

20 kWh sur une fenêtre de 2 h avec une borne de 7,4 kW (monophasé 32 A) ⇒
14,8 kWh placés (2 × 7,4) et 5,2 kWh en ``energie_non_placee_kwh`` — le cas
cité par la tâche.

Test PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.charges import ChargeInvalide, courbe_vehicule

# 200 km/j à 10 kWh/100 km = 20 kWh/j, sur une fenêtre de 2 heures.
VEHICULE_20KWH_2H = dict(km_par_jour=200.0, kwh_par_100km=10.0,
                         fenetre_recharge=[10, 11])


class BorneDePuissanceTest(unittest.TestCase):

    def test_20kwh_sur_2h_avec_borne_7_4kw_donne_14_8_places_et_5_2_non_places(self):
        charge = courbe_vehicule(**VEHICULE_20KWH_2H,
                                 puissance_borne_kw=7.4)
        self.assertAlmostEqual(charge['energie_journaliere_kwh'], 20.0,
                               places=4)
        self.assertAlmostEqual(sum(charge['courbe']), 14.8, places=2)
        self.assertAlmostEqual(charge['energie_non_placee_kwh'], 5.2,
                               places=2)
        self.assertTrue(any('trop court' in h.lower()
                            for h in charge['hypotheses']))
        for heure in (10, 11):
            self.assertLessEqual(charge['courbe'][heure], 7.4 + 1e-9)

    def test_sans_puissance_borne_la_courbe_reste_celle_d_aujourd_hui(self):
        charge = courbe_vehicule(**VEHICULE_20KWH_2H)
        self.assertEqual(charge['energie_non_placee_kwh'], 0.0)
        valeurs_actives = {charge['courbe'][h] for h in (10, 11)}
        self.assertEqual(len(valeurs_actives), 1)
        self.assertAlmostEqual(list(valeurs_actives)[0], 10.0, places=4)

    def test_puissance_negative_est_refusee_en_nommant_le_champ(self):
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_vehicule(**VEHICULE_20KWH_2H, puissance_borne_kw=-7.4)
        self.assertEqual(refus.exception.champ, 'vehicule.puissance_borne_kw')

    def test_borne_suffisante_ne_laisse_aucun_reliquat(self):
        charge = courbe_vehicule(**VEHICULE_20KWH_2H,
                                 puissance_borne_kw=22.0)
        self.assertEqual(charge['energie_non_placee_kwh'], 0.0)
        self.assertAlmostEqual(sum(charge['courbe']), 20.0, places=4)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
