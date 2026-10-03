# -*- coding: utf-8 -*-
"""AGR110 — la table unique des hypothèses de pompage (noyau pur, sans base).

* chaque entrée a un statut connu et une source (ou ``EST.`` explicite) ;
* ``hypotheses_pompage.json`` est ÉGAL à l'export de la table — le test RELIT
  l'échantillon, il ne le recopie jamais ;
* aucune clé de bassin n'entre dans le noyau (NE PAS FAIRE du Groupe AGR).
"""

import ast
import json
import os
import re
import unittest

from core.pompage import hypotheses as H

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE_DJANGO = os.path.dirname(os.path.dirname(ICI))
ECHANTILLON = os.path.join(RACINE_DJANGO, "apps", "ventes", "contract_samples",
                           "hypotheses_pompage.json")
PAQUET = os.path.join(RACINE_DJANGO, "core", "pompage")


class ChaqueEntreeEstSourcee(unittest.TestCase):

    def test_statut_usage_et_source(self):
        self.assertTrue(H.TABLE)
        for entree in H.TABLE:
            self.assertIn(entree.statut, H.STATUTS, entree.cle)
            self.assertIn(entree.usage, H.USAGES, entree.cle)
            self.assertTrue(entree.source and entree.source.strip(), entree.cle)

    def test_les_estimations_sont_marquees_est(self):
        rendement = H.hypothese("rendement_groupe")
        self.assertEqual(rendement.statut, "EST.")
        self.assertIn("0,35-0,55", rendement.source)

    def test_cles_uniques(self):
        cles = [e.cle for e in H.TABLE]
        self.assertEqual(len(cles), len(set(cles)))

    def test_constante_physique_coherente(self):
        # ρ·g/3600 avec ρ = 1000 kg/m³ et g = 9,81 m/s² (J → Wh).
        self.assertAlmostEqual(H.valeur("energie_hydraulique_wh_par_m3_m"),
                               1000 * 9.81 / 3600, places=3)
        self.assertAlmostEqual(H.valeur("cv_vers_kw"), 0.7355, places=6)

    def test_tolerance_jamais_seuil_de_recette(self):
        tol = H.hypothese("tolerance_conception_pct")
        self.assertEqual(tol.usage, "controle_conception")
        self.assertEqual(tol.statut, "source_secondaire")

    def test_indications_jamais_un_calcul(self):
        for cle in ("part_debit_essai_pct", "pression_goutte_a_goutte_bar"):
            self.assertEqual(H.hypothese(cle).usage, "indication")

    def test_cle_inconnue_leve(self):
        with self.assertRaises(KeyError):
            H.hypothese("inexistante")

    def test_utilisees_filtre_dans_l_ordre(self):
        sortie = H.utilisees({"hazen_williams_c_pvc_pehd",
                              "energie_hydraulique_wh_par_m3_m"})
        self.assertEqual([e["cle"] for e in sortie],
                         ["energie_hydraulique_wh_par_m3_m",
                          "hazen_williams_c_pvc_pehd"])

    def test_table_rend_des_dicts_neufs(self):
        a = H.table()
        a[0]["valeur"] = 999
        self.assertNotEqual(H.table()[0]["valeur"], 999)


class EchantillonEgalALExport(unittest.TestCase):

    def test_echantillon_relu_egal_a_l_export(self):
        with open(ECHANTILLON, "r", encoding="utf-8") as fh:
            echantillon = json.load(fh)
        self.assertEqual(echantillon["exemple"], H.export())

    def test_hypotheses_de_l_apercu_sont_des_entrees_de_la_table(self):
        chemin = os.path.join(os.path.dirname(ECHANTILLON),
                              "etude_pompage_preview.json")
        with open(chemin, "r", encoding="utf-8") as fh:
            contrat = json.load(fh)
        table = {e["cle"]: e for e in H.table()}
        for cle_exemple, exemple in contrat.items():
            if not cle_exemple.startswith("exemple"):
                continue
            for entree in exemple.get("hypotheses") or []:
                self.assertEqual(entree, table[entree["cle"]], entree["cle"])


class AucunBassinDansLeNoyau(unittest.TestCase):
    """Aucun bassin dimensionné ni « ×2 » (seule l'autonomie d'un réservoir
    DÉCLARÉ est calculée, AGR116)."""

    MOTIF = re.compile(r"bassin|reservoir_mult|multiplicateur", re.IGNORECASE)

    def test_aucune_cle_de_bassin_dans_la_table(self):
        fautives = [e.cle for e in H.TABLE if self.MOTIF.search(e.cle)]
        self.assertEqual(fautives, [])

    def test_aucune_constante_de_bassin_au_niveau_module(self):
        fautifs = []
        for nom in sorted(os.listdir(PAQUET)):
            if not nom.endswith(".py"):
                continue
            with open(os.path.join(PAQUET, nom), "r", encoding="utf-8") as fh:
                arbre = ast.parse(fh.read())
            for noeud in arbre.body:
                if isinstance(noeud, (ast.Assign, ast.AnnAssign)):
                    cibles = ([noeud.target] if isinstance(noeud, ast.AnnAssign)
                              else noeud.targets)
                    for cible in cibles:
                        if (isinstance(cible, ast.Name)
                                and self.MOTIF.search(cible.id)):
                            fautifs.append((nom, cible.id))
        self.assertEqual(fautifs, [])
