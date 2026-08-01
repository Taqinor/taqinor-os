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

#: empreintes des scripts témoins — ``docs/ao-frdisi/`` est GELÉ.
#: Empreintes prises sur le contenu NORMALISÉ en fins de ligne LF, c'est-à-dire
#: sur les octets tels que git les stocke : un poste Windows avec
#: ``core.autocrlf=true`` reçoit les mêmes fichiers en CRLF, ce qui changerait
#: l'empreinte brute sans qu'une seule ligne de code ait bougé. Le gel porte sur
#: le CONTENU des témoins, pas sur la convention de fin de ligne du poste.
EMPREINTES_TEMOINS = (
    ("vue_bat_A_v2.py",
     "ae7aad9f7937be4cf977b4e38e0d19e261c59df89bb466a4767fafcc901977bc"),
    ("vue_bat_B_v2.py",
     "f0821f0a36b275156708785fae330bb1a819a3a00b247db18476f35ec9ef19fb"),
    ("vue_bat_C.py",
     "086df93782dcb3bed5dd9d0415b3deecf07db58ce2adb5d655078fc1ef63c68d"),
    ("calepinage.py",
     "56e4ff98292e924b1d4337409dd7049c5105bce2b5098b633503e7d559ef7484"),
    ("solveur.py",
     "57e108fcee7908153dc1a6770d3fbfbbecc31077ca1ab9ab6a80c2637dab0ae4"),
)


def _empreinte_temoin(chemin):
    """SHA-256 du témoin, fins de ligne normalisées en LF.

    Reproduit exactement la normalisation de git : seul ``\\r\\n`` devient
    ``\\n``. L'empreinte est donc la même sous Linux (CI) et sous Windows.
    """
    with io.open(chemin, "rb") as fh:
        contenu = fh.read()
    return hashlib.sha256(contenu.replace(b"\r\n", b"\n")).hexdigest()


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
            obtenue = _empreinte_temoin(chemin)
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
