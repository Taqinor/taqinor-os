# -*- coding: utf-8 -*-
"""AOF183 — goldens FRDISI : réconciliation, écartés présents, comptes verrouillés.

Trois tests SANS base de données : les goldens sont des documents JSON du
contrat ``EntreeCalepinage``, rejoués par le moteur pur. Les comptes sont ceux
des scripts TÉMOINS du 27/07/2026, réconciliés par
``scripts/reconcilier_calepinage_frdisi.py`` : bâtiment A 148, bâtiment B 120,
bâtiment C 314.
"""

import hashlib
import io
import json
import os
import unittest

from core.calepinage.moteur import compter_plan
from core.calepinage.poseur import poser_plan
from core.calepinage.serialisation import EntreeCalepinage
from core.calepinage.types import Provenance

#: racine du dépôt : core/tests -> core -> django_core -> backend -> racine
RACINE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "..", "..", ".."))
GOLDEN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "calepinage", "golden", "frdisi_2026_07_27")
TEMOINS = os.path.join(RACINE, "docs", "ao-frdisi", "releve-2026-07-27")

#: comptes RÉCONCILIÉS contre les scripts témoins
COMPTES = (("bat_A_aile_L.json", 148), ("bat_C_ecole.json", 314),
           ("bat_B_arc.json", 120))

#: empreintes des scripts témoins — ``docs/ao-frdisi/`` est GELÉ
EMPREINTES_TEMOINS = (
    ("vue_bat_A_v2.py",
     "67d58c58aece0613e6decf7acb00513c9375c1614378fd3d501182e5595e8f9a"),
    ("vue_bat_B_v2.py",
     "1fdac754478b787ba030d0dc7ab1467979c1840bc724827cb46947b221168292"),
    ("vue_bat_C.py",
     "d38f43aa2c2656a188f5185beb5d27868b904e56f78872c698b2b5608d776e21"),
    ("calepinage.py",
     "50e8d588a4aea2aab6ba3123b156a668506404aaad0c4984653391747e77d546"),
    ("solveur.py",
     "887cb1187ccbbace867ed6d240f09e292c6317704bc0a90f4c8a3ae4149baf1a"),
)


def _document(nom):
    with io.open(os.path.join(GOLDEN, nom), encoding="utf-8") as fh:
        return json.load(fh)


def _compte_simple(document):
    """Bâtiments A et C : une surface, un jeu de rangées explicites."""
    entree = EntreeCalepinage.depuis_dict(
        {k: v for k, v in document.items() if k != "golden"})
    kit = entree.parametres.kits[0]
    rangees = tuple((y, kit) for y in document["golden"]["rangees_retenues"])
    return entree, compter_plan(entree.surfaces[0], rangees, entree.obstacles)


def _compte_arc(document):
    """Bâtiment B : 3 segments, chacun son plan de pose et son kit."""
    entree = EntreeCalepinage.depuis_dict(
        {k: v for k, v in document.items() if k != "golden"})
    par_repere = {s.repere: s for s in entree.surfaces}
    total = 0
    for segment in document["golden"]["segments"]:
        surface = par_repere[segment["repere"]]
        kit = [k for k in entree.kits if k.code == segment["kit"]][0]
        # les obstacles du golden sont en abscisse LOCALE de leur segment :
        # le golden dit lesquels appartiennent à CE segment
        vises = set(segment["obstacles"])
        obstacles = tuple(o for o in entree.obstacles if o.repere in vises)
        rangees = tuple((y, kit) for y in segment["rangees_retenues"])
        total += compter_plan(surface, rangees, obstacles).modules
    return entree, total


class LesTroisBatimentsRedonnentLeursComptes(unittest.TestCase):
    def test_bat_a_aile_l_redonne_148(self):
        document = _document("bat_A_aile_L.json")
        _entree, plan = _compte_simple(document)
        self.assertEqual(plan.modules, 148)
        self.assertEqual(document["golden"]["compte_temoin"], 148)

    def test_bat_c_ecole_redonne_314(self):
        document = _document("bat_C_ecole.json")
        _entree, plan = _compte_simple(document)
        self.assertEqual(plan.modules, 314)
        self.assertEqual(document["golden"]["compte_temoin"], 314)

    def test_bat_b_arc_redonne_120(self):
        document = _document("bat_B_arc.json")
        _entree, total = _compte_arc(document)
        self.assertEqual(total, 120)
        self.assertEqual(document["golden"]["compte_temoin"], 120)

    def test_le_total_du_site_est_calcule(self):
        total = 0
        for nom, _attendu in COMPTES:
            document = _document(nom)
            if nom == "bat_B_arc.json":
                total += _compte_arc(document)[1]
            else:
                total += _compte_simple(document)[1].modules
        self.assertEqual(total, 148 + 314 + 120)

    def test_les_engagements_du_bordereau_sont_portes(self):
        engagements = {}
        for nom, _attendu in COMPTES:
            for repere, modules in _document(nom)["engagements"]:
                engagements[repere] = modules
        self.assertEqual(engagements["BAT_A_AILE_L"], 152)
        self.assertEqual(engagements["BAT_C_ECOLE"], 288)
        self.assertEqual(engagements["BAT_B_ARC"], 120)
        self.assertEqual(sum(engagements.values()), 560)


class DessineEgaleCompteSurLesGoldens(unittest.TestCase):
    def test_le_poseur_confirme_le_compteur(self):
        for nom in ("bat_A_aile_L.json", "bat_C_ecole.json"):
            document = _document(nom)
            entree, plan = _compte_simple(document)
            kit = entree.parametres.kits[0]
            rangees = tuple((y, kit)
                            for y in document["golden"]["rangees_retenues"])
            tables = poser_plan(entree.surfaces[0], rangees, entree.obstacles)
            self.assertEqual(kit.modules_par_pas * len(tables), plan.modules,
                             nom)


class LesEcartesFigurentAvecLeurProvenance(unittest.TestCase):
    def test_les_quatre_souches_de_l_ecole_sont_presentes_et_ecartees(self):
        document = _document("bat_C_ecole.json")
        souches = [o for o in document["obstacles"]
                   if o["repere"].startswith("SOUCHE_")]
        self.assertEqual(len(souches), 4)
        for souche in souches:
            self.assertEqual(souche["provenance"], Provenance.ECARTE.value)
            self.assertIn("ÉCARTÉE", souche["regle_appliquee"])
            self.assertIn("NON RELEVÉE", souche["regle_appliquee"])

    def test_les_ecartes_ne_comptent_pas(self):
        document = _document("bat_C_ecole.json")
        _entree, plan = _compte_simple(document)
        self.assertEqual(plan.modules, 314)

    def test_grect_et_pan_sont_conserves_et_identifies(self):
        document = _document("bat_A_aile_L.json")
        par_repere = {o["repere"]: o for o in document["obstacles"]}
        self.assertEqual(par_repere["GRECT"]["provenance"],
                         Provenance.DEVINE.value)
        self.assertEqual(par_repere["PAN"]["provenance"],
                         Provenance.PLAN.value)
        for repere in ("GRECT", "PAN"):
            obstacle = par_repere[repere]
            self.assertLess(obstacle["x0"], obstacle["x1"])
            self.assertLess(obstacle["y0"], obstacle["y1"])

    def test_les_28_emprises_relevees_de_l_aile_l_sont_la(self):
        document = _document("bat_A_aile_L.json")
        relevees = [o for o in document["obstacles"]
                    if o["provenance"] in (Provenance.RELEVE.value,
                                           Provenance.RELEVE_DOUTEUX.value)]
        self.assertEqual(len(relevees), 28)


class LesTemoinsSontGeles(unittest.TestCase):
    def test_les_scripts_d_origine_sont_inchanges(self):
        for nom, empreinte in EMPREINTES_TEMOINS:
            chemin = os.path.join(TEMOINS, nom)
            self.assertTrue(os.path.exists(chemin), "témoin absent : %s" % nom)
            with io.open(chemin, "rb") as fh:
                obtenue = hashlib.sha256(fh.read()).hexdigest()
            self.assertEqual(obtenue, empreinte,
                             "docs/ao-frdisi/ est GELÉ : %s a été modifié"
                             % nom)


class LesGoldensSontDesEntreesValides(unittest.TestCase):
    def test_aller_retour_json_sans_perte(self):
        for nom, _attendu in COMPTES:
            document = _document(nom)
            entree = EntreeCalepinage.depuis_dict(
                {k: v for k, v in document.items() if k != "golden"})
            refaite = EntreeCalepinage.depuis_json(entree.vers_json())
            self.assertEqual(refaite.hash_entree, entree.hash_entree, nom)

    def test_le_hash_d_entree_est_fige_dans_le_golden(self):
        for nom in ("bat_A_aile_L.json", "bat_C_ecole.json"):
            document = _document(nom)
            entree = EntreeCalepinage.depuis_dict(
                {k: v for k, v in document.items() if k != "golden"})
            self.assertEqual(entree.hash_entree,
                             document["golden"]["hash_entree"], nom)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
