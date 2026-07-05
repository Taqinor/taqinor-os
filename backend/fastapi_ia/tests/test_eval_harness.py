"""YHARD12 — harnais d'evaluation de la QUALITE FONCTIONNELLE de l'agent
NL->SQL (au-dela de la securite, deja couverte par test_sql_security.py /
test_infra_hardening.py / test_margin_guard.py / test_action_tools.py).

100% offline / deterministe : aucune cle ni appel LLM (mode "fixtures d'or" —
voir tests/eval/runner.py). Se saute proprement si sql_agent_service (et ses
dependances lourdes, langchain notamment) n'est pas importable, comme le reste
de la suite fastapi_ia.

A lancer depuis backend/fastapi_ia :
    python -m unittest tests.test_eval_harness -v
"""
import os
import sys
import unittest

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.eval import runner  # noqa: E402
from tests.eval.cases import CASES  # noqa: E402


@unittest.skipUnless(
    runner.eval_available(),
    f"sql_agent_service non importable: {runner.import_error()}",
)
class EvalHarnessTests(unittest.TestCase):
    """Score chaque cas metier individuellement — un echec pointe precisement
    vers le cas fautif (plutot qu'un seul test agrege opaque)."""

    def test_all_business_cases_individually(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                result = runner.score_case(case)
                self.assertTrue(result["passed"], result["reason"])

    def test_prompt_leak_case(self):
        result = runner.score_prompt_leak_case()
        self.assertTrue(result["passed"], result["reason"])

    def test_run_eval_score_above_threshold(self):
        report = runner.run_eval()
        self.assertGreaterEqual(report["score"], 0.9, report["results"])

    def test_run_eval_or_raise_passes_at_default_threshold(self):
        # Ne doit PAS lever au seuil par defaut (0.9) : le jeu de cas fourni
        # est concu pour etre 100% vert (y compris le cas negatif
        # d'hallucination, qui doit ECHOUER-COMME-ATTENDU pour etre compte
        # "passed").
        report = runner.run_eval_or_raise(threshold=0.9)
        self.assertEqual(report["passed"], report["total"])

    def test_hallucination_case_is_flagged_not_silently_accepted(self):
        """Le cas negatif volontaire (table hors allowlist) doit etre detecte
        par le harnais — jamais silencieusement traite comme correct."""
        hallucination_case = next(
            c for c in CASES if c["id"] == "hallucination_table_inexistante")
        self.assertTrue(hallucination_case.get("expect_failure"))
        tables = runner._tables_of(hallucination_case["gold_sql"])
        self.assertFalse(tables.issubset(set(
            runner.svc._ALLOWED_TABLES)))  # confirme que c'est bien hors-liste
        result = runner.score_case(hallucination_case)
        # "passed" ici signifie "le harnais a correctement flag l'anomalie".
        self.assertTrue(result["passed"])

    def test_regression_case_that_should_fail_does_fail(self):
        """Sanity check du harnais lui-meme : un SQL DML injecte comme
        producer factice doit faire echouer le cas correspondant (le harnais
        n'accepte pas n'importe quoi)."""
        case = CASES[0]

        def bad_producer(_question):
            return "DELETE FROM stock_produit"

        result = runner.score_case(case, sql_producer=bad_producer)
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
