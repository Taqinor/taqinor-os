# -*- coding: utf-8 -*-
"""AOF53 — l'échelle de l'arc A=112 → F=120 → H=126, avec ses assertions.

Chaque marche est REJOUÉE par le moteur courant. Falsifier un ``attendu`` doit
rendre le test rouge EN NOMMANT la marche.
"""

import unittest

from core.calepinage.echelle import (
    MONOTONIES_STANDARD,
    Echelle,
    EtatNomme,
    MonotonieMetier,
    comparer,
    verifier_honnetete,
    verifier_monotonies,
)
from core.calepinage.exceptions import CalepinageIncoherent
from core.calepinage.moteur import compter_plan
from core.calepinage.pose_uniforme import balayer_phase
from core.calepinage.types import KIT_AO_PAYSAGE, Marche, Parametres
from core.tests.test_calepinage_pose_uniforme import (
    ARC_KITS,
    ARC_RANGEES,
    RIVES_AO,
    RIVES_V1,
    obstacles_arc,
    segment_arc,
    segment_plat,
)

SEGMENTS = ("S1", "S2", "S3")
#: rangées recalées du segment 3 (marche H)
S3_RECALE = (0.95, 4.85, 8.30)
#: rangées « tout paysage » du segment 1 (marche E)
S1_PAYSAGE = (1.55, 5.45, 8.30)


def _uniforme(allee, rives, degagement, corrige):
    """Somme des 3 segments en mode uniforme à phase balayée."""
    parametres = Parametres(kits=(KIT_AO_PAYSAGE,), rives=rives, allee_m=allee)
    total = 0
    for segment in SEGMENTS:
        surface = (segment_arc(segment, rives) if corrige
                   else segment_plat(segment, rives))
        total += balayer_phase(surface, parametres,
                               obstacles_arc(segment, degagement)).modules
    return total


def _explicite(kits, rangees=None, exclure=()):
    """Somme des 3 segments en rangées explicites."""
    total = 0
    for segment in SEGMENTS:
        surface = segment_arc(segment, RIVES_AO)
        kit = kits.get(segment, ARC_KITS[segment])
        rows = (rangees or {}).get(segment, ARC_RANGEES[segment])
        obstacles = tuple(o for o in obstacles_arc(segment)
                          if o.repere not in exclure)
        total += compter_plan(surface, tuple((y, kit) for y in rows),
                              obstacles).modules
    return total


def echelle_de_l_arc():
    """Les 8 marches du bâtiment B, chacune REJOUABLE."""
    return comparer((
        EtatNomme("A", "ancien modèle : uniforme 1,20, tables jointives en "
                       "abscisse développée",
                  lambda: _uniforme(1.20, RIVES_V1, 0.30, corrige=False),
                  attendu=112),
        EtatNomme("B", "durcissement de la correction d'arc",
                  lambda: _uniforme(1.20, RIVES_V1, 0.30, corrige=True),
                  attendu=108),
        EtatNomme("C", "dégagement 0,30 → 0,35 en abscisse développée",
                  lambda: _uniforme(1.20, RIVES_V1, 0.35, corrige=True),
                  attendu=100),
        EtatNomme("D", "allées 0,60 et rives d'extrémité 0,35",
                  lambda: _uniforme(0.60, RIVES_AO, 0.35, corrige=True),
                  attendu=104),
        EtatNomme("E", "rangées explicites, tout paysage",
                  lambda: _explicite({"S1": KIT_AO_PAYSAGE},
                                     {"S1": S1_PAYSAGE}),
                  attendu=114),
        EtatNomme("F", "segment 1 en tables portrait (chiffre PUBLIÉ)",
                  lambda: _explicite({}), attendu=120),
        EtatNomme("G", "structures de rive non cotées hors zone PV",
                  lambda: _explicite({}, exclure=("N1", "N2")), attendu=126),
        EtatNomme("H", "recalage du segment 3",
                  lambda: _explicite({}, {"S3": S3_RECALE},
                                     exclure=("N1", "N2")), attendu=126),
    ))


class LEchelleDeLArc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.echelle = echelle_de_l_arc()

    def test_les_huit_marches_sont_calculees(self):
        self.assertEqual(len(self.echelle.marches), 8)
        self.assertEqual(tuple(m.code for m in self.echelle.marches),
                         ("A", "B", "C", "D", "E", "F", "G", "H"))

    def test_a_vaut_112_f_vaut_120_h_vaut_126(self):
        self.assertEqual(self.echelle.marche("A").modules, 112)
        self.assertEqual(self.echelle.marche("F").modules, 120)
        self.assertEqual(self.echelle.marche("H").modules, 126)

    def test_les_deltas_sont_signes(self):
        deltas = {m.code: m.delta for m in self.echelle.marches}
        self.assertEqual(deltas["A"], 0)
        self.assertEqual(deltas["B"], -4)
        self.assertEqual(deltas["F"], 6)
        self.assertEqual(deltas["G"], 6)

    def test_le_recit_est_genere(self):
        recit = self.echelle.recit()
        self.assertIn("112", recit)
        self.assertIn("126", recit)
        self.assertIn("+14", recit)
        self.assertEqual(self.echelle.gain_total, 14)

    def test_les_assertions_d_honnetete_passent(self):
        self.assertEqual(verifier_honnetete(self.echelle), ())

    def test_les_monotonies_metier_passent(self):
        self.assertEqual(verifier_monotonies(self.echelle), ())

    def test_marche_inconnue(self):
        with self.assertRaises(KeyError):
            self.echelle.marche("Z")


class FalsifierUneMarcheRendRouge(unittest.TestCase):
    def test_un_attendu_faux_nomme_la_marche(self):
        echelle = comparer((
            EtatNomme("A", "ancien modèle", lambda: 112, attendu=112),
            EtatNomme("F", "publié", lambda: 120, attendu=999),
        ))
        with self.assertRaises(CalepinageIncoherent) as ctx:
            verifier_honnetete(echelle)
        self.assertEqual(ctx.exception.repere, "F")
        self.assertIn("attendu 999", str(ctx.exception))

    def test_le_mode_non_strict_rend_les_motifs(self):
        echelle = comparer((
            EtatNomme("A", "ancien", lambda: 100, attendu=112),
        ))
        motifs = verifier_honnetete(echelle, strict=False)
        self.assertEqual(len(motifs), 1)
        self.assertIn("marche A", motifs[0])

    def test_une_marche_sans_attendu_est_libre(self):
        echelle = comparer((EtatNomme("X", "exploratoire", lambda: 42),))
        self.assertEqual(verifier_honnetete(echelle), ())


class MonotoniesMetier(unittest.TestCase):
    def test_retirer_un_obstacle_ne_peut_pas_faire_perdre(self):
        echelle = comparer((
            EtatNomme("F", "avec obstacles", lambda: 120),
            EtatNomme("G", "sans les non-cotés", lambda: 110),
        ))
        with self.assertRaises(CalepinageIncoherent) as ctx:
            verifier_monotonies(echelle)
        self.assertIn("monotonie non tenue", str(ctx.exception))

    def test_un_kit_unique_ne_peut_pas_battre_le_mixte(self):
        echelle = comparer((
            EtatNomme("MIXTE", "kits mixtes", lambda: 172),
            EtatNomme("UNIQUE", "kit unique", lambda: 148),
        ))
        regle = MonotonieMetier("UNIQUE", "MIXTE", ">=",
                                "le kit unique ne peut pas battre le mixte")
        self.assertEqual(verifier_monotonies(echelle, (regle,)), ())

    def test_les_monotonies_standard_sont_publiees(self):
        self.assertEqual(len(MONOTONIES_STANDARD), 2)
        for regle in MONOTONIES_STANDARD:
            self.assertTrue(regle.libelle)

    def test_sens_de_monotonie_invalide(self):
        with self.assertRaises(ValueError):
            MonotonieMetier("A", "B", "!=")

    def test_une_regle_sur_un_code_absent_est_ignoree(self):
        echelle = comparer((EtatNomme("A", "seule", lambda: 10),))
        self.assertEqual(verifier_monotonies(echelle), ())


class EchelleVide(unittest.TestCase):
    def test_echelle_vide(self):
        echelle = Echelle(marches=())
        self.assertEqual(echelle.depart, 0)
        self.assertEqual(echelle.arrivee, 0)
        self.assertEqual(echelle.recit(), "aucune marche")

    def test_marche_est_immuable(self):
        marche = Marche(code="A", libelle="x", modules=112, delta=0)
        with self.assertRaises(Exception):
            marche.modules = 0


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
