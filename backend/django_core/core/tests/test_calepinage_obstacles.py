# -*- coding: utf-8 -*-
"""AOF35 — provenance × type → dégagement dérivé, règle tracée, engageabilité."""

import unittest

from core.calepinage.obstacles import (
    DEGAGEMENT_PAR_PROVENANCE,
    DEGAGEMENT_PAR_TYPE,
    appliquer_regles,
    degagement_effectif,
    engageable,
    fusionner,
    intervalles_bloques,
)
from core.calepinage.types import Obstacle, Provenance, TypeObstacle


def _obs(repere, x0, x1, y0, y1, **kw):
    return Obstacle(repere=repere, x0=x0, x1=x1, y0=y0, y1=y1, **kw)


class TablesCompletes(unittest.TestCase):
    def test_les_13_types_et_les_6_provenances_sont_couverts(self):
        self.assertEqual(len(DEGAGEMENT_PAR_TYPE), len(list(TypeObstacle)))
        self.assertEqual(len(DEGAGEMENT_PAR_TYPE), 13)
        self.assertEqual(len(DEGAGEMENT_PAR_PROVENANCE), len(list(Provenance)))
        self.assertEqual(len(DEGAGEMENT_PAR_PROVENANCE), 6)


class DegagementDerive(unittest.TestCase):
    def test_type_seul_quand_la_provenance_est_relevee(self):
        valeur, regle = degagement_effectif(
            _obs("C1", 0, 1, 0, 1, type_obstacle=TypeObstacle.CAISSON_BETON,
                 provenance=Provenance.RELEVE))
        self.assertAlmostEqual(valeur, 0.30)
        self.assertIn("CAISSON_BETON", regle)

    def test_provenance_douteuse_impose_le_traitement_nature_inconnue(self):
        valeur, regle = degagement_effectif(
            _obs("C6", 0, 1, 0, 1, type_obstacle=TypeObstacle.CAISSON_BETON,
                 provenance=Provenance.RELEVE_DOUTEUX))
        self.assertAlmostEqual(valeur, 0.50)
        self.assertIn("RELEVE_DOUTEUX", regle)

    def test_surcharge_explicite_gagne(self):
        valeur, regle = degagement_effectif(
            _obs("NOTCH", 0, 1, 0, 1, type_obstacle=TypeObstacle.CAISSON_BETON,
                 provenance=Provenance.RELEVE, degagement_m=0.35))
        self.assertAlmostEqual(valeur, 0.35)
        self.assertIn("surcharge", regle)

    def test_la_regle_est_ecrite_dans_le_resultat(self):
        obs = appliquer_regles((
            _obs("SOUCHE", 0, 1, 0, 1, type_obstacle=TypeObstacle.SOUCHE),
        ))
        self.assertAlmostEqual(obs[0].degagement_m, 0.50)
        self.assertTrue(obs[0].regle_appliquee)
        self.assertIn("SOUCHE", obs[0].regle_appliquee)


class Engageabilite(unittest.TestCase):
    def test_un_obstacle_du_plan_rend_non_engageable_avec_motif_nomme(self):
        ok, motifs = engageable((
            _obs("PAN", 0, 1, 0, 1, provenance=Provenance.PLAN),
        ))
        self.assertFalse(ok)
        self.assertEqual(len(motifs), 1)
        self.assertIn("PAN", motifs[0])
        self.assertIn("PLAN", motifs[0])

    def test_un_obstacle_devine_rend_non_engageable(self):
        ok, motifs = engageable((
            _obs("GRECT", 0, 1, 0, 1, provenance=Provenance.DEVINE),
        ))
        self.assertFalse(ok)
        self.assertIn("DEVINÉE", motifs[0])

    def test_releve_et_declare_client_sont_engageables(self):
        ok, motifs = engageable((
            _obs("C1", 0, 1, 0, 1, provenance=Provenance.RELEVE),
            _obs("C2", 0, 1, 0, 1, provenance=Provenance.RELEVE_DOUTEUX),
            _obs("C3", 0, 1, 0, 1, provenance=Provenance.DECLARE_CLIENT),
        ))
        self.assertTrue(ok)
        self.assertEqual(motifs, ())

    def test_ecarte_conserve_la_geometrie_et_sort_du_compte(self):
        brut = _obs("S1", 3.0, 4.0, 0.0, 1.0, provenance=Provenance.ECARTE,
                    type_obstacle=TypeObstacle.SOUCHE)
        obs = appliquer_regles((brut,))
        self.assertAlmostEqual(obs[0].x0, 3.0)      # géométrie CONSERVÉE
        self.assertAlmostEqual(obs[0].x1, 4.0)
        self.assertAlmostEqual(obs[0].degagement_m, 0.0)
        self.assertIn("ÉCARTÉ", obs[0].regle_appliquee)
        ok, _motifs = engageable(obs)
        self.assertTrue(ok)                          # n'empêche pas l'engagement
        self.assertEqual(intervalles_bloques(obs, 0.0, 1.0, 0.0, 10.0), ())


class FusionEtBlocage(unittest.TestCase):
    def test_fusion_d_intervalles(self):
        self.assertEqual(fusionner([(0.0, 1.0), (0.9, 2.0), (3.0, 4.0)]),
                         ((0.0, 2.0), (3.0, 4.0)))
        self.assertEqual(fusionner([(1.0, 1.0)]), ())

    def test_intervalles_bloques_applique_le_degagement(self):
        obs = appliquer_regles((
            _obs("C", 5.0, 6.0, 0.0, 1.0, type_obstacle=TypeObstacle.CAISSON_BETON),
        ))
        bloques = intervalles_bloques(obs, 0.0, 1.0, 0.0, 20.0)
        self.assertEqual(len(bloques), 1)
        self.assertAlmostEqual(bloques[0][0], 4.70)
        self.assertAlmostEqual(bloques[0][1], 6.30)

    def test_bande_hors_portee_n_est_pas_bloquee(self):
        obs = appliquer_regles((
            _obs("C", 5.0, 6.0, 0.0, 1.0, type_obstacle=TypeObstacle.CAISSON_BETON),
        ))
        self.assertEqual(intervalles_bloques(obs, 5.0, 6.0, 0.0, 20.0), ())

    def test_degagement_non_derive_leve(self):
        with self.assertRaises(ValueError):
            intervalles_bloques((_obs("C", 5.0, 6.0, 0.0, 1.0),), 0.0, 1.0, 0.0, 20.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
