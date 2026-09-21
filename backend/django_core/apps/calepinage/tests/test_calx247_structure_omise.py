# -*- coding: utf-8 -*-
"""CALX247 — la structure QUITTE la nomenclature électrique sans règle sourcée.

``core/electrique/nomenclature.py`` posait trois lignes de fixation (rails,
pinces, crochets) par des ratios écrits en dur (``nb_modules * 2``,
``nb_modules * 2 + 4``, ``max(4, ceil(nb_modules * 0.6))``), sans aucune
source. Décision fondateur 21/09/2026 (registre
``services/parametres_cles.py::CLES_ELECTRIQUE_SOCIETE``, clé
``regle_bom_structure``) : la structure sort du bordereau électrique quand
personne ne l'a sourcée — les trois lignes sont alors OMISES, jamais
rendues à zéro ni devinées.

Test de SURFACE (AST, sur le modèle de
``apps/calepinage/tests/test_lestage_parametre.py::AucuneConstanteNormativeTest``,
lui-même sur ``services/lestage.py:85``) : la fonction qui calcule les
quantités de structure ne contient PLUS aucun littéral numérique — les
ratios viennent exclusivement de la règle saisie.

``SimpleTestCase`` pur — aucune base.
"""

import ast
import pathlib
import unittest

from django.test import SimpleTestCase

from core.electrique.nomenclature import (
    MOTIF_STRUCTURE_NON_SOURCEE,
    nomenclature,
)
from core.electrique.types import EntreeElectrique, GroupePan, SpecModule, SpecOnduleur

MODULE = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                    pmax_wc=550.0)
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                        v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=10.0)

REGLE_SOURCEE = {
    'rails_par_module': 2.0,
    'pinces_par_module': 2.0,
    'pinces_supplement': 4.0,
    'crochets_par_module': 0.6,
    'crochets_minimum': 4.0,
    'source': "Cahier de pose K2 Base, système standard toiture inclinée",
}


def _entree(nb_modules=18):
    return EntreeElectrique(
        module=MODULE, onduleur=ONDULEUR,
        groupes=(GroupePan("Sud", nb_modules, 180.0, 15.0),))


def _lignes_structure(resultat):
    return [ligne for ligne in resultat.lignes if ligne.categorie == "Structure"]


class ReglesSaisieTroisLignesSourcees(SimpleTestCase):
    def test_regle_saisie_rend_trois_lignes_sourcees(self):
        resultat = nomenclature(_entree(18), regle_bom_structure=REGLE_SOURCEE)
        lignes = _lignes_structure(resultat)
        self.assertEqual(len(lignes), 3)
        for ligne in lignes:
            self.assertIn(REGLE_SOURCEE['source'], ligne.spec)
            self.assertGreater(ligne.quantite, 0)

    def test_les_quantites_suivent_la_regle_saisie(self):
        resultat = nomenclature(_entree(20), regle_bom_structure=REGLE_SOURCEE)
        lignes = {ligne.designation: ligne.quantite
                  for ligne in _lignes_structure(resultat)}
        self.assertEqual(lignes["Rail de fixation aluminium"], 40.0)
        self.assertEqual(
            lignes["Pince de fixation (milieu + extrémité)"], 44.0)
        self.assertEqual(
            lignes["Crochet / patte de fixation toiture"], 12.0)

    def test_une_regle_differente_change_les_quantites(self):
        autre_regle = dict(REGLE_SOURCEE, rails_par_module=3.0,
                           source="Cahier de pose Schletter Rapid16")
        resultat_defaut = nomenclature(_entree(18),
                                       regle_bom_structure=REGLE_SOURCEE)
        resultat_autre = nomenclature(_entree(18),
                                      regle_bom_structure=autre_regle)
        rails_defaut = next(
            ligne.quantite for ligne in _lignes_structure(resultat_defaut)
            if ligne.designation == "Rail de fixation aluminium")
        rails_autre = next(
            ligne.quantite for ligne in _lignes_structure(resultat_autre)
            if ligne.designation == "Rail de fixation aluminium")
        self.assertNotEqual(rails_defaut, rails_autre)


class AucuneRegleZeroLigneMotifPublie(SimpleTestCase):
    def test_aucune_regle_zero_ligne_et_motif(self):
        resultat = nomenclature(_entree(18))
        self.assertEqual(_lignes_structure(resultat), [])
        self.assertIn(MOTIF_STRUCTURE_NON_SOURCEE, resultat.alertes)

    def test_regle_sans_source_zero_ligne(self):
        sans_source = dict(REGLE_SOURCEE, source="")
        resultat = nomenclature(_entree(18), regle_bom_structure=sans_source)
        self.assertEqual(_lignes_structure(resultat), [])
        self.assertIn(MOTIF_STRUCTURE_NON_SOURCEE, resultat.alertes)

    def test_regle_avec_champ_illisible_nomme_le_champ(self):
        illisible = dict(REGLE_SOURCEE, crochets_par_module="beaucoup")
        resultat = nomenclature(_entree(18), regle_bom_structure=illisible)
        self.assertEqual(_lignes_structure(resultat), [])
        motifs = " | ".join(resultat.alertes)
        self.assertIn("crochets_par_module", motifs)


class LeResteDuBordereauNeBougePas(SimpleTestCase):
    """Le retrait de la structure ne touche NI le câblage, NI les protections."""

    def test_les_lignes_non_structure_sont_identiques_avec_ou_sans_regle(self):
        sans_regle = nomenclature(_entree(18))
        avec_regle = nomenclature(_entree(18), regle_bom_structure=REGLE_SOURCEE)
        non_structure_sans = [ligne for ligne in sans_regle.lignes
                              if ligne.categorie != "Structure"]
        non_structure_avec = [ligne for ligne in avec_regle.lignes
                              if ligne.categorie != "Structure"]
        self.assertEqual(non_structure_sans, non_structure_avec)


class AucunLitteralDeStructureTest(unittest.TestCase):
    """Test de SURFACE : ``_lignes_structure`` ne porte plus AUCUN nombre."""

    def test_aucun_litteral_numerique_dans_lignes_structure(self):
        chemin = (pathlib.Path(__file__).resolve().parent.parent.parent.parent
                  / 'core' / 'electrique' / 'nomenclature.py')
        arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        fonction = next(
            noeud for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.FunctionDef)
            and noeud.name == '_lignes_structure')
        intrus = []
        for noeud in ast.walk(fonction):
            if isinstance(noeud, ast.Constant) and isinstance(
                    noeud.value, (int, float)) and not isinstance(
                    noeud.value, bool):
                intrus.append((noeud.lineno, noeud.value))
        self.assertEqual(
            intrus, [],
            "Constante numérique dans _lignes_structure "
            "(core/electrique/nomenclature.py) : une quantité de structure "
            "se SAISIT avec sa source (regle_bom_structure), elle ne "
            "s'écrit jamais dans le code (CALX247).")
