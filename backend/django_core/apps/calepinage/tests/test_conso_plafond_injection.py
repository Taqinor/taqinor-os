"""CAL151 — le plafond d'injection au POINT DE LIVRAISON.

Ce qui est tenu :

* l'énergie écrêtée est publiée SÉPARÉMENT (kWh + heures concernées) ;
* plafond vide ⇒ aucun écrêtage appliqué ET rien d'affiché (jamais un
  « 0 kWh écrêté », qui se lirait comme un plafond vérifié) ;
* un plafond sans justification est REFUSÉ en nommant le champ.

Tests PURS : aucune base, aucun réseau.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.autoconsommation import (
    BilanInvalide, bilan_autoconsommation, plafond_injection,
)

CONSO_PLATE = [1.0] * 24
PROD_CLOCHE = ([0.0] * 6 + [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
               + [6.0, 5.0, 4.0, 3.0, 2.0, 1.0] + [0.0] * 6)
JUSTIFICATION = 'Contrat de raccordement ONEE n° 12345, puissance injectable.'


class PlafondVideTest(unittest.TestCase):

    def test_sans_plafond_rien_n_est_ecrete_ni_affiche(self):
        bloc = plafond_injection([5.0, 9.0, 1.0])
        self.assertFalse(bloc['applique'])
        self.assertIsNone(bloc['plafond_kw'])
        # Ni 0 kWh, ni 0 heure : RIEN — un zéro se lirait « vérifié ».
        self.assertIsNone(bloc['energie_ecretee_kwh'])
        self.assertIsNone(bloc['heures_ecretees'])
        self.assertEqual(bloc['surplus_apres_ecretage'], [5.0, 9.0, 1.0])

    def test_le_bilan_ne_publie_aucun_bloc_plafond(self):
        bilan = bilan_autoconsommation(CONSO_PLATE, PROD_CLOCHE)
        self.assertIsNone(bilan['plafond'])


class EcretageTest(unittest.TestCase):

    def test_l_energie_ecretee_et_les_heures_sont_publiees(self):
        bloc = plafond_injection([1.0, 4.0, 6.0, 0.0], plafond_kw=3.0,
                                 justification=JUSTIFICATION)
        self.assertTrue(bloc['applique'])
        self.assertEqual(bloc['surplus_apres_ecretage'],
                         [1.0, 3.0, 3.0, 0.0])
        self.assertEqual(bloc['energie_ecretee_kwh'], 4.0)
        self.assertEqual(bloc['heures_ecretees'], 2)

    def test_un_plafond_au_dessus_du_pic_n_ecrete_rien_mais_le_dit(self):
        bloc = plafond_injection([1.0, 2.0], plafond_kw=10.0,
                                 justification=JUSTIFICATION)
        self.assertTrue(bloc['applique'])
        self.assertEqual(bloc['energie_ecretee_kwh'], 0.0)
        self.assertEqual(bloc['heures_ecretees'], 0)

    def test_le_plafond_s_applique_heure_par_heure_dans_le_bilan(self):
        bilan = bilan_autoconsommation(
            CONSO_PLATE, PROD_CLOCHE, plafond_injection_kw=2.0,
            justification_plafond=JUSTIFICATION)
        bloc = bilan['plafond']
        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['plafond_kw'], 2.0)
        self.assertGreater(bloc['energie_ecretee_kwh'], 0.0)
        self.assertTrue(all(valeur <= 2.0
                            for valeur in bloc['surplus_apres_ecretage']))

    def test_la_justification_accompagne_le_plafond(self):
        bloc = plafond_injection([5.0], plafond_kw=1.0,
                                 justification=JUSTIFICATION)
        self.assertEqual(bloc['justification'], JUSTIFICATION)

    def test_un_pas_different_d_une_heure_convertit_les_kw_en_kwh(self):
        """Un pas de 30 min : 4 kW valent 2 kWh sur le pas."""
        bloc = plafond_injection([3.0], plafond_kw=4.0, pas_heures=0.5,
                                 justification=JUSTIFICATION)
        self.assertEqual(bloc['surplus_apres_ecretage'], [2.0])
        self.assertEqual(bloc['energie_ecretee_kwh'], 1.0)


class RefusTest(unittest.TestCase):

    def test_un_plafond_sans_justification_est_refuse(self):
        with self.assertRaises(BilanInvalide) as refus:
            plafond_injection([5.0], plafond_kw=3.0)
        self.assertEqual(refus.exception.champ,
                         'plafond_injection_justification')
        self.assertIn('contrat', str(refus.exception).lower())

    def test_un_plafond_illisible_est_refuse_en_nommant_le_champ(self):
        with self.assertRaises(BilanInvalide) as refus:
            plafond_injection([5.0], plafond_kw='beaucoup',
                              justification=JUSTIFICATION)
        self.assertEqual(refus.exception.champ, 'plafond_injection_kw')

    def test_un_plafond_negatif_est_refuse(self):
        with self.assertRaises(BilanInvalide):
            plafond_injection([5.0], plafond_kw=-1.0,
                              justification=JUSTIFICATION)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
