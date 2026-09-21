"""CALX264 — le COP de la pompe à chaleur dépend de la température saisie.

Ce qui est tenu :

* ``cop_points`` (au moins deux points SAISIS) interpole LINÉAIREMENT le COP
  entre les points, selon la température de chaque heure active
  (``temperature_horaire``) ;
* hors de la plage saisie, AUCUNE extrapolation : le point extrême le plus
  proche est employé, et la mention le dit ;
* ``cop`` scalaire reste le comportement d'AUJOURD'HUI quand ``cop_points``
  est absent (non-régression du test CAL154 existant) ;
* une seule entrée dans ``cop_points`` est refusée en nommant le champ.

Les points (-7 ; 2,31) et (10 ; 5,19) sont ceux CITÉS par la tâche comme
exemple de saisie documenté par PV*SOL (plage A-7/W35 → A10/W35 —
https://help.valentin-software.com/pvsol/en/calculation/thermal-system/) :
ils ne sont JAMAIS employés comme un défaut, seulement comme l'entrée d'un
test qui vérifie l'interpolation.

Test PUR : aucune base, aucun réseau.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.charges import ChargeInvalide, courbe_pac

POINTS_PVSOL = [
    {'t_ext_c': -7, 'cop': 2.31},
    {'t_ext_c': 10, 'cop': 5.19},
]

# Une seule heure active (1h) pour isoler proprement le COP interpolé de
# cette heure dans `energie_journaliere_kwh` / `parametres.cop_moyen_actif`.
TEMPERATURE_1_5_A_1H = [1.5 if heure == 1 else -99.0 for heure in range(24)]


class CopPointsInterpolationTest(unittest.TestCase):

    def test_interpolation_lineaire_a_1_5_degres_donne_3_75(self):
        charge = courbe_pac(
            puissance_kw=1.0, cop_points=POINTS_PVSOL,
            temperature_horaire=TEMPERATURE_1_5_A_1H,
            heures_fonctionnement=[1])
        self.assertAlmostEqual(
            charge['parametres']['cop_moyen_actif'], 3.75, delta=0.01)
        # Puissance 1 kW, facteur de saison par défaut 1 ⇒ l'énergie de
        # l'heure active vaut directement 1 / COP interpolé.
        self.assertAlmostEqual(charge['energie_journaliere_kwh'],
                               1.0 / 3.75, delta=0.001)

    def test_hors_plage_basse_utilise_le_point_extreme_et_le_dit(self):
        temperatures = [-20.0 if heure == 1 else -99.0 for heure in range(24)]
        charge = courbe_pac(
            puissance_kw=1.0, cop_points=POINTS_PVSOL,
            temperature_horaire=temperatures, heures_fonctionnement=[1])
        self.assertAlmostEqual(
            charge['parametres']['cop_moyen_actif'], 2.31, delta=0.001)
        self.assertTrue(any('extrapolation' in h.lower()
                            or 'hors' in h.lower()
                            for h in charge['hypotheses']))

    def test_hors_plage_haute_utilise_le_point_extreme(self):
        temperatures = [30.0 if heure == 1 else -99.0 for heure in range(24)]
        charge = courbe_pac(
            puissance_kw=1.0, cop_points=POINTS_PVSOL,
            temperature_horaire=temperatures, heures_fonctionnement=[1])
        self.assertAlmostEqual(
            charge['parametres']['cop_moyen_actif'], 5.19, delta=0.001)

    def test_une_seule_entree_de_cop_points_est_refusee(self):
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_pac(
                puissance_kw=1.0, cop_points=[POINTS_PVSOL[0]],
                temperature_horaire=TEMPERATURE_1_5_A_1H,
                heures_fonctionnement=[1])
        self.assertEqual(refus.exception.champ, 'pac.cop_points')

    def test_cop_points_sans_temperature_horaire_est_refuse(self):
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_pac(puissance_kw=1.0, cop_points=POINTS_PVSOL,
                       heures_fonctionnement=[1])
        self.assertEqual(refus.exception.champ, 'pac.temperature_horaire')

    def test_temperature_horaire_mal_dimensionnee_est_refusee(self):
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_pac(puissance_kw=1.0, cop_points=POINTS_PVSOL,
                       temperature_horaire=[1.5] * 23,
                       heures_fonctionnement=[1])
        self.assertEqual(refus.exception.champ, 'pac.temperature_horaire')


class CopPointsAbsentComportementScalaireTest(unittest.TestCase):
    """``cop_points`` absent ⇒ EXACTEMENT le comportement d'aujourd'hui."""

    PAC_SCALAIRE = dict(puissance_kw=3.0, cop=3.5,
                        heures_fonctionnement=[6, 7, 18, 19])

    def test_l_energie_electrique_est_la_thermique_divisee_par_le_cop(self):
        charge = courbe_pac(**self.PAC_SCALAIRE)
        self.assertAlmostEqual(charge['energie_journaliere_kwh'],
                               3.0 * 4 / 3.5, places=4)

    def test_aucun_cop_par_defaut_sans_cop_points(self):
        entree = dict(self.PAC_SCALAIRE)
        entree.pop('cop')
        with self.assertRaises(ChargeInvalide) as refus:
            courbe_pac(**entree)
        self.assertEqual(refus.exception.champ, 'pac.cop')

    def test_la_repartition_reste_uniforme_sans_cop_points(self):
        charge = courbe_pac(**self.PAC_SCALAIRE)
        valeurs_actives = {charge['courbe'][h] for h in (6, 7, 18, 19)}
        self.assertEqual(len(valeurs_actives), 1)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
