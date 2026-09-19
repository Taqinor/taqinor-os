# -*- coding: utf-8 -*-
"""CAL166 — ``schema.json`` NE PEUT PLUS diverger du code qu'il décrit.

Le schéma publié n'énumérait que deux modes de pose et ne déclarait ni
``rangees_imposees`` ni ``phase_forcee_m`` : le troisième mode (PV29/PV31,
servi par le studio AO) passait seulement parce que ``$defs.parametres`` n'est
pas strict. Un contrat qui ment silencieusement n'est pas un contrat.

Ces tests dérivent les attentes du CODE (``ModePose``, ``Parametres``,
``_parametres``) au lieu de recopier une liste : ajouter demain un mode ou un
paramètre sérialisé sans l'écrire dans ``schema.json`` rend ce fichier ROUGE.

Aucune base de données, aucune dépendance nouvelle : ``unittest`` + ``json``
(``jsonschema`` n'est pas au ``requirements`` du dépôt, on ne l'y ajoute pas
pour un test).
"""

import io
import json
import os
import unittest

from core.calepinage.serialisation import EntreeCalepinage, _parametres
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PORTRAIT,
    ModePose,
    Parametres,
    Rives,
)
from core.calepinage.version import SCHEMA_VERSION

CALEPINAGE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "calepinage")
CHEMIN_SCHEMA = os.path.join(CALEPINAGE, "schema.json")
GOLDEN = os.path.join(CALEPINAGE, "golden", "frdisi_2026_07_27")


def _schema():
    with io.open(CHEMIN_SCHEMA, encoding="utf-8") as fh:
        return json.load(fh)


def _proprietes_parametres():
    return _schema()["$defs"]["parametres"]["properties"]


def _parametres_imposes():
    """Des ``Parametres`` qui exercent les TROIS champs longtemps absents."""
    return Parametres(
        kits=(KIT_AO_PORTRAIT,),
        rives=Rives(laterale_m=0.30, extremite_m=0.30),
        mode_pose=ModePose.RANGEES_IMPOSEES_UTILISATEUR,
        rangees_imposees=((0.35, KIT_AO_PORTRAIT.code),
                          (6.95, KIT_AO_PORTRAIT.code)),
        phase_forcee_m=0.12)


class LeSchemaDecritTousLesModesDePose(unittest.TestCase):
    def test_l_enum_mode_pose_couvre_l_enumere_du_code(self):
        enum = _proprietes_parametres()["mode_pose"]["enum"]
        self.assertEqual(sorted(enum), sorted(m.value for m in ModePose))

    def test_le_mode_impose_utilisateur_est_declare(self):
        # C'était la divergence exacte de CAL166 : le mode PV29/PV31 était
        # sérialisé par le code et absent du contrat publié.
        self.assertIn(ModePose.RANGEES_IMPOSEES_UTILISATEUR.value,
                      _proprietes_parametres()["mode_pose"]["enum"])


class LeSchemaDeclareToutCeQueLeCodeSerialise(unittest.TestCase):
    def test_aucune_cle_serialisee_n_est_absente_du_schema(self):
        declarees = set(_proprietes_parametres())
        for parametres in (Parametres(kits=(KIT_AO_PORTRAIT,)),
                           _parametres_imposes()):
            emises = set(_parametres(parametres))
            manquantes = sorted(emises - declarees)
            self.assertEqual(manquantes, [],
                             "clés sérialisées absentes de schema.json : %s"
                             % manquantes)

    def test_rangees_imposees_et_phase_forcee_sont_declarees(self):
        declarees = _proprietes_parametres()
        for cle in ("rangees_imposees", "phase_forcee_m"):
            self.assertIn(cle, declarees)
            # Absent vaut None : le type doit tolérer explicitement null,
            # sinon un document qui porte le champ à vide serait refusé.
            self.assertIn("null", declarees[cle]["type"])

    def test_une_rangee_imposee_est_un_couple_position_code(self):
        item = _proprietes_parametres()["rangees_imposees"]["items"]
        self.assertEqual(item["minItems"], 2)
        self.assertEqual(item["maxItems"], 2)
        self.assertEqual([p["type"] for p in item["prefixItems"]],
                         ["number", "string"])


class LesDocumentsExistantsRestentConformes(unittest.TestCase):
    def test_les_golden_n_emettent_aucune_cle_non_declaree(self):
        declarees = set(_proprietes_parametres())
        for nom in sorted(os.listdir(GOLDEN)):
            if not nom.endswith(".json"):
                continue
            with io.open(os.path.join(GOLDEN, nom), encoding="utf-8") as fh:
                document = json.load(fh)
            manquantes = sorted(set(document["parametres"]) - declarees)
            self.assertEqual(manquantes, [], "%s : %s" % (nom, manquantes))

    def test_un_document_impose_fait_l_aller_retour(self):
        entree = EntreeCalepinage(
            repere="PV31",
            surfaces=(SurfaceRectangle(repere="PV31", longueur_m=20.0,
                                       largeur_m=12.0),),
            kits=(KIT_AO_PORTRAIT,), parametres=_parametres_imposes())
        document = entree.vers_dict()
        self.assertEqual(document["parametres"]["mode_pose"],
                         ModePose.RANGEES_IMPOSEES_UTILISATEUR.value)
        self.assertEqual(document["parametres"]["phase_forcee_m"], 0.12)
        refaite = EntreeCalepinage.depuis_json(entree.vers_json())
        self.assertEqual(refaite.hash_entree, entree.hash_entree)
        self.assertEqual(refaite.parametres.rangees_imposees,
                         entree.parametres.rangees_imposees)


class LAlignementNeChangeAucuneEmpreinte(unittest.TestCase):
    """CAL166 corrige une DOCUMENTATION : rien de publiable ne bouge.

    ``schema_version`` entre dans ``vers_dict()``, donc dans ``hash_entree`` :
    l'incrémenter ferait dériver les empreintes GELÉES des golden et de toutes
    les études déjà persistées. Le raisonnement est consigné dans
    ``version.py`` ; ce test l'ARME.
    """

    def test_le_schema_reste_en_version_1(self):
        self.assertEqual(SCHEMA_VERSION, 1)

    def test_l_empreinte_gelee_de_l_ecole_est_intacte(self):
        with io.open(os.path.join(GOLDEN, "bat_C_ecole.json"),
                     encoding="utf-8") as fh:
            document = json.load(fh)
        entree = EntreeCalepinage.depuis_dict(
            {k: v for k, v in document.items() if k != "golden"})
        self.assertEqual(entree.hash_entree,
                         document["golden"]["hash_entree"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
