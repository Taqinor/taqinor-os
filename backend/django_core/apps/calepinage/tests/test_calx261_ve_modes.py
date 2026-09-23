"""CALX261 — les deux modes de recharge du véhicule électrique.

Ce qui est tenu :

* ``mode='immediat'`` (défaut) conserve EXACTEMENT le comportement
  d'aujourd'hui — répartition uniforme sur la fenêtre saisie ;
* ``mode='pv_optimise'`` exige ``vehicule.production_horaire`` et place
  l'énergie d'abord sur les heures de plus grand SURPLUS de production dans
  la fenêtre saisie ; le véhicule charge quand même le reliquat que le
  surplus ne couvre pas — ce reliquat vient du RÉSEAU (``energie_reseau_kwh``),
  JAMAIS masqué, et il est réparti uniformément (comme le mode immédiat)
  puisque le véhicule doit physiquement charger ce reliquat quelque part ;
* un surplus qui suffit à couvrir toute l'énergie ⇒ ``energie_reseau_kwh``
  vaut zéro ;
* un surplus NUL sur toute la fenêtre ⇒ toute l'énergie est réseau et la
  courbe rendue est IDENTIQUE à celle du mode ``immediat`` (seule la source
  change, pas le geste de charge) ;
* ``pv_optimise`` sans ``production_horaire`` est REFUSÉ en nommant le champ.

Test PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.charges import ChargeInvalide, courbe_vehicule

VEHICULE_BASE = dict(km_par_jour=100.0, kwh_par_100km=15.0,
                     fenetre_recharge=[22, 23, 0, 1])


class ModeImmediatTest(unittest.TestCase):
    """Le mode ``immediat`` (défaut) est un pur NON-régression de CAL154."""

    def test_defaut_est_immediat(self):
        avec_defaut = courbe_vehicule(**VEHICULE_BASE)
        explicite = courbe_vehicule(**VEHICULE_BASE, mode='immediat')
        self.assertEqual(avec_defaut['courbe'], explicite['courbe'])
        self.assertEqual(explicite['parametres']['mode'], 'immediat')

    def test_repartition_uniforme_terme_a_terme(self):
        charge = courbe_vehicule(**VEHICULE_BASE, mode='immediat')
        energie = charge['energie_journaliere_kwh']
        valeurs_actives = {charge['courbe'][h] for h in (22, 23, 0, 1)}
        self.assertEqual(len(valeurs_actives), 1)
        self.assertAlmostEqual(list(valeurs_actives)[0], energie / 4,
                               places=6)
        self.assertEqual(charge['energie_reseau_kwh'], 0.0)

    def test_mode_inconnu_est_refuse(self):
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_vehicule(**VEHICULE_BASE, mode='turbo')
        self.assertEqual(refus.exception.champ, 'vehicule.mode')


class ModePvOptimiseTest(unittest.TestCase):

    def test_surplus_suffisant_donne_energie_reseau_nulle(self):
        charge_immediate = courbe_vehicule(**VEHICULE_BASE, mode='immediat')
        energie = charge_immediate['energie_journaliere_kwh']
        # Un surplus largement suffisant sur chacune des 4 heures actives.
        production = [0.0] * 24
        for heure in (22, 23, 0, 1):
            production[heure] = energie
        charge = courbe_vehicule(**VEHICULE_BASE, mode='pv_optimise',
                                 production_horaire=production)
        self.assertEqual(charge['energie_reseau_kwh'], 0.0)
        self.assertAlmostEqual(sum(charge['courbe']), energie, places=4)

    def test_surplus_nul_rend_toute_l_energie_reseau_et_la_courbe_immediate(self):
        charge_immediate = courbe_vehicule(**VEHICULE_BASE, mode='immediat')
        production = [0.0] * 24  # aucun surplus nulle part
        charge = courbe_vehicule(**VEHICULE_BASE, mode='pv_optimise',
                                 production_horaire=production)
        self.assertAlmostEqual(charge['energie_reseau_kwh'],
                               charge['energie_journaliere_kwh'], places=4)
        for attendu, obtenu in zip(charge_immediate['courbe'],
                                   charge['courbe']):
            self.assertAlmostEqual(attendu, obtenu, places=4)

    def test_sans_production_horaire_est_refuse_en_nommant_le_champ(self):
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_vehicule(**VEHICULE_BASE, mode='pv_optimise')
        self.assertEqual(refus.exception.champ,
                         'vehicule.production_horaire')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
