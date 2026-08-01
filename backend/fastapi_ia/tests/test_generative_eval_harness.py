"""NTAI32 — harnais d'evaluation des features IA GENERATIVES (extension YHARD12).

100% offline / deterministe : aucune cle, aucun appel LLM, aucune dependance
lourde. Contrairement a ``test_eval_harness.py`` (agent NL->SQL), ce module ne
se saute PAS quand ``sql_agent_service`` est indisponible : il n'evalue pas ce
service, seulement les proprietes de sorties generatives fixtures.

A lancer depuis backend/fastapi_ia :
    python -m unittest tests.test_generative_eval_harness -v
"""
import os
import sys
import unittest

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.eval import generative_runner as gr  # noqa: E402
from tests.eval.generative_cases import (  # noqa: E402
    BROUILLON_CASES, EXTRACTION_CASES, FAMILLES_REQUISES, GENERATIVE_CASES,
    RESUME_CASES, SEUIL_DEFAUT)


class GenerativeEvalHarnessTests(unittest.TestCase):
    def test_chaque_cas_individuellement(self):
        """Un echec pointe le cas fautif, pas un score agrege opaque."""
        for case in GENERATIVE_CASES:
            with self.subTest(case=case["id"]):
                result = gr.score_generative_case(case)
                self.assertTrue(result["passed"], result["reason"])

    def test_couvre_resume_brouillon_extraction(self):
        self.assertEqual(gr.familles_couvertes(), set(FAMILLES_REQUISES))
        self.assertTrue(RESUME_CASES and BROUILLON_CASES and EXTRACTION_CASES)

    def test_score_au_dessus_du_seuil(self):
        report = gr.run_generative_eval()
        self.assertGreaterEqual(report["score"], SEUIL_DEFAUT,
                                report["results"])
        self.assertEqual(report["passed"], report["total"])

    def test_or_raise_ne_leve_pas_au_seuil_par_defaut(self):
        report = gr.run_generative_eval_or_raise(threshold=SEUIL_DEFAUT)
        self.assertEqual(report["passed"], report["total"])

    # ── Le harnais a-t-il des dents ? ───────────────────────────────────────
    def test_echoue_sous_le_seuil(self):
        """Une sortie systematiquement mauvaise doit FAIRE ECHOUER la porte."""
        def producer_mauvais(_case):
            return ""

        with self.assertRaises(AssertionError):
            gr.run_generative_eval_or_raise(threshold=SEUIL_DEFAUT,
                                            producer=producer_mauvais)

    def test_pii_en_clair_detectee(self):
        self.assertIn("cin", gr._contient_pii("Le client CIN AB123456 a paye."))
        self.assertIn("email",
                      gr._contient_pii("Ecrire a client@example.com svp."))
        self.assertIn("telephone",
                      gr._contient_pii("Rappeler au 0612345678 demain."))
        self.assertEqual(gr._contient_pii("Aucune donnee personnelle ici."), [])

    def test_nom_de_table_sql_detecte(self):
        self.assertIn(
            "crm_client",
            gr._noms_de_tables_cites("selon crm_client, ce prospect…"))
        self.assertEqual(gr._noms_de_tables_cites("Rien de technique ici."), [])

    def test_cas_negatif_non_declenche_est_signale(self):
        """Un cas marque `attendu_en_echec` dont la sortie est en fait BONNE
        doit etre compte comme un ECHEC du harnais (trop laxiste)."""
        faux_negatif = {
            "id": "sanity", "feature": "brouillon", "sortie": "Bonjour.",
            "non_vide": True, "attendu_en_echec": True,
        }
        result = gr.score_generative_case(faux_negatif)
        self.assertFalse(result["passed"])
        self.assertIn("laxiste", result["reason"])

    def test_famille_manquante_refusee(self):
        """Vider une famille de cas ne doit pas donner un 100% trompeur."""
        with self.assertRaises(AssertionError):
            gr.run_generative_eval(cases=RESUME_CASES)

    def test_extraction_cle_inventee_est_refusee(self):
        case = next(c for c in EXTRACTION_CASES
                    if c["id"] == "extraction_cle_inventee_refusee")
        echecs = gr._verifier_extraction(case, case["sortie"])
        self.assertTrue(any('hors schema' in e for e in echecs), echecs)

    def test_deterministe(self):
        """Mode fixtures : deux executions donnent EXACTEMENT le meme rapport
        (aucun appel LLM, donc aucune variance possible)."""
        premier = gr.run_generative_eval()
        second = gr.run_generative_eval()
        self.assertEqual(premier["results"], second["results"])
        self.assertEqual(premier["score"], second["score"])


if __name__ == "__main__":
    unittest.main()
