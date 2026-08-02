# -*- coding: utf-8 -*-
"""AOF184 — goldens d'échelle et de sensibilité : les assertions du script
d'origine deviennent des TESTS.

Trois familles, toutes sans base de données :

* l'ÉCHELLE de l'arc — A = 112 (ancien modèle) → F = 120 (publié) →
  H = 126 (segment 3 recalé), avec ses 8 deltas signés ;
* les SENSIBILITÉS de l'aile en L et son PLANCHER publié ;
* la CONTRE-ÉPREUVE de kit par segment — S2 paysage 34 contre portrait 24,
  S3 paysage 44 contre portrait 42 : aucun de ces quatre chiffres n'est écrit
  à la main dans le moteur, ils sortent tous du compteur.
"""

import unittest

from core.calepinage.echelle import (
    MonotonieMetier,
    verifier_honnetete,
    verifier_monotonies,
)
from core.calepinage.moteur import compter_plan
from core.calepinage.types import KIT_AO_PAYSAGE, KIT_AO_PORTRAIT
from core.tests.test_calepinage_echelle import echelle_de_l_arc
from core.tests.test_calepinage_pose_uniforme import (
    ARC_RANGEES,
    RIVES_AO,
    obstacles_arc,
    segment_arc,
)
from core.tests.test_calepinage_sensibilites import (
    ATTENDUS_AILE_L,
    _batterie,
)

#: l'échelle complète, marche par marche (code, modules, delta signé)
ECHELLE_ATTENDUE = (
    ("A", 112, 0), ("B", 108, -4), ("C", 100, -8), ("D", 104, 4),
    ("E", 114, 10), ("F", 120, 6), ("G", 126, 6), ("H", 126, 0),
)
#: rangées portrait de contre-épreuve (2 rangées de 4,70 sur 10,90)
RANGEES_PORTRAIT = (0.55, 5.85)
#: contre-épreuve de kit PAR SEGMENT (paysage, portrait), hors non-cotés
CONTRE_EPREUVE = (("S2", 34, 24, ()), ("S3", 44, 42, ("N1", "N2")))


def _compte(segment, kit, rangees, exclure=()):
    surface = segment_arc(segment, RIVES_AO)
    obstacles = tuple(o for o in obstacles_arc(segment)
                      if o.repere not in exclure)
    return compter_plan(surface, tuple((y, kit) for y in rangees),
                        obstacles).modules


class LEchelleCompleteEstReproduite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.echelle = echelle_de_l_arc()

    def test_les_huit_marches_et_leurs_deltas(self):
        obtenue = tuple((m.code, m.modules, m.delta)
                        for m in self.echelle.marches)
        self.assertEqual(obtenue, ECHELLE_ATTENDUE)

    def test_le_recit_ancien_vers_aujourd_hui(self):
        self.assertEqual(self.echelle.marche("A").modules, 112)
        self.assertEqual(self.echelle.marche("F").modules, 120)
        self.assertEqual(self.echelle.marche("H").modules, 126)
        self.assertEqual(self.echelle.gain_total, 14)

    def test_les_assertions_d_honnetete_sont_vertes(self):
        self.assertEqual(verifier_honnetete(self.echelle), ())

    def test_falsifier_une_marche_nomme_la_marche(self):
        from core.calepinage.echelle import EtatNomme, comparer
        from core.calepinage.exceptions import CalepinageIncoherent

        falsifiee = comparer((
            EtatNomme("F", "publié", lambda: 120, attendu=126),))
        with self.assertRaises(CalepinageIncoherent) as ctx:
            verifier_honnetete(falsifiee)
        self.assertEqual(ctx.exception.repere, "F")

    def test_les_monotonies_metier(self):
        self.assertEqual(verifier_monotonies(self.echelle), ())

    def test_retirer_un_obstacle_ne_peut_pas_faire_perdre(self):
        regle = MonotonieMetier("F", "G", ">=",
                                "retirer un obstacle ne peut pas faire perdre")
        self.assertEqual(verifier_monotonies(self.echelle, (regle,)), ())

    def test_un_recalage_ne_peut_pas_faire_perdre(self):
        regle = MonotonieMetier("G", "H", ">=",
                                "un recalage ne peut pas faire perdre")
        self.assertEqual(verifier_monotonies(self.echelle, (regle,)), ())


class LesSensibilitesDeLAileL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.batterie = _batterie()

    def test_la_reference_est_le_compte_du_temoin(self):
        self.assertEqual(self.batterie.reference, 148)

    def test_chaque_sensibilite_est_reproduite_a_l_unite(self):
        obtenus = {s.code: s.modules for s in self.batterie.sensibilites}
        for code, attendu in ATTENDUS_AILE_L:
            self.assertEqual(obtenus[code], attendu, "sensibilité %s" % code)

    def test_le_plancher_publie_est_celui_du_moteur(self):
        self.assertEqual(self.batterie.plancher, 102)
        pire = min(s.modules for s in self.batterie.sensibilites)
        self.assertEqual(self.batterie.plancher, min(pire,
                                                     self.batterie.reference))

    def test_le_verdict_est_genere_et_porte_le_plancher(self):
        verdict = self.batterie.verdict()
        self.assertIn(str(self.batterie.plancher), verdict)

    def test_les_deltas_defavorables_sont_negatifs(self):
        perdantes = self.batterie.sensibilites_perdantes
        self.assertTrue(perdantes)
        for sensibilite in perdantes:
            self.assertLess(sensibilite.delta, 0)


class LaContreEpreuveDeKitParSegment(unittest.TestCase):
    """``assert n_alt <= n_show`` du script d'origine, chiffré par segment."""

    def test_s2_paysage_34_contre_portrait_24(self):
        self.assertEqual(_compte("S2", KIT_AO_PAYSAGE, ARC_RANGEES["S2"]), 34)
        self.assertEqual(_compte("S2", KIT_AO_PORTRAIT, RANGEES_PORTRAIT), 24)

    def test_s3_paysage_44_contre_portrait_42(self):
        self.assertEqual(
            _compte("S3", KIT_AO_PAYSAGE, ARC_RANGEES["S3"], ("N1", "N2")), 44)
        self.assertEqual(
            _compte("S3", KIT_AO_PORTRAIT, RANGEES_PORTRAIT, ("N1", "N2")), 42)

    def test_le_kit_retenu_est_toujours_le_meilleur_du_segment(self):
        for segment, paysage, portrait, exclure in CONTRE_EPREUVE:
            self.assertGreaterEqual(paysage, portrait,
                                    "segment %s" % segment)
            self.assertEqual(
                _compte(segment, KIT_AO_PAYSAGE, ARC_RANGEES[segment],
                        exclure), paysage)
            self.assertEqual(
                _compte(segment, KIT_AO_PORTRAIT, RANGEES_PORTRAIT, exclure),
                portrait)

    def test_le_segment_1_est_l_inverse_et_c_est_pourquoi_il_est_portrait(self):
        """Sur S1, le portrait GAGNE (48 contre 42) — d'où la marche F."""
        self.assertEqual(_compte("S1", KIT_AO_PORTRAIT, ARC_RANGEES["S1"]), 48)
        self.assertEqual(_compte("S1", KIT_AO_PAYSAGE, (1.55, 5.45, 8.30)), 42)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
