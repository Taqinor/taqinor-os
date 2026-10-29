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

from tests.eval import runner  # noqa: E402 — après sys.path/setup() (D-ENF22)
from tests.eval.cases import CASES  # noqa: E402 — après sys.path/setup() (D-ENF22)


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

    def test_rejeu_reel_commerciaux(self):
        """Rejeu PAYANT, desarme par defaut : sans ASSISTANT_EVAL=1 + cle +
        SQL_AGENT_JUGE_MODEL il ne fait rien (pas de nouveau site de saut :
        la baseline ENF23 ne grossit pas, C20)."""
        if not (os.environ.get("ASSISTANT_EVAL") == "1"
                and os.environ.get("CLAUDE_API_KEY")
                and os.environ.get("SQL_AGENT_JUGE_MODEL")):
            return
        modele = runner.svc._modele_effectif(runner.svc.SQL_AGENT_PROVIDER.lower())
        juge = os.environ["SQL_AGENT_JUGE_MODEL"]
        # AIC13 (29/10/2026) : avec ASSISTANT_EVAL_TOKEN (jeton d acces du
        # commercial evalue), le rejeu porte les outils d action du registre ;
        # sans jeton, l agent repond en lecture seule (cas donnee/action non jouables).
        ctx = None
        jeton = os.environ.get("ASSISTANT_EVAL_TOKEN", "").strip()
        if jeton:
            from app.services.action_tools import ActionContext, resolve_caller_permissions
            ctx = ActionContext(
                company_id=int(os.environ.get("ASSISTANT_EVAL_COMPANY_ID", "1")),
                role="normal", permissions=[], token=jeton, is_superuser=False)
            resolve_caller_permissions(ctx)
        rapport = runner.run_eval_commerciaux(
            runner.repondeur_reel(int(os.environ.get("ASSISTANT_EVAL_COMPANY_ID", "1")),
                                  int(os.environ.get("ASSISTANT_EVAL_USER_ID", "1")), ctx),
            runner.juge_reel(juge), modele, juge)
        self.assertTrue(os.path.exists(runner.ecrire_rapport(rapport)))


class EvalCommerciauxTests(unittest.TestCase):
    """AIC10 — jeu de 50 questions de commerciaux, fournisseur SIMULE (aucun
    appel payant) ; le rejeu reel exige ASSISTANT_EVAL=1 + une cle."""

    @staticmethod
    def _repondre(case):
        return {"answer": "ok", "outils_appeles": [case["outil"]] if case["outil"] else [],
                "sql_query": "SELECT 1" if case["outil"] == "sql_db_query" else "",
                "tokens": {"cache_read": 1000, "input": 200, "output": 100}}

    @staticmethod
    def _juger(case, _reponse):
        return {c: True for c in runner.CRITERES_JUGE}

    def test_jeu_de_50_cas_cinq_par_intention(self):
        from tests.eval.cases_commerciaux import CASES_COMMERCIAUX, INTENTIONS_ATTENDUES
        self.assertEqual(len(CASES_COMMERCIAUX), 50)
        self.assertEqual(len({c["id"] for c in CASES_COMMERCIAUX}), 50)
        base = [c for c in CASES_COMMERCIAUX if c["source"] == "base"]
        for intention in INTENTIONS_ATTENDUES:
            self.assertEqual(sum(c["intention"] == intention for c in base), 5, intention)
        self.assertEqual(sum(c["source"] == "guide" for c in CASES_COMMERCIAUX), 20)

    def test_texte_du_message_saute_le_bloc_de_reflexion(self):
        """AIC13 : Haiku 5.5 repond [ThinkingBlock, TextBlock] ; le juge lit le texte."""
        class Bloc:
            def __init__(self, type, text=None):
                self.type = type
                if text is not None:
                    self.text = text
        self.assertEqual(runner.texte_du_message(
            [Bloc("thinking"), Bloc("text", "{\"exacte\": true}")]), "{\"exacte\": true}")
        self.assertEqual(runner.texte_du_message([{"type": "text", "text": "ok"}]), "ok")
        self.assertEqual(runner.texte_du_message([]), "")

    def test_juge_different_du_modele_evalue(self):
        with self.assertRaises(ValueError):
            runner.run_eval_commerciaux(self._repondre, self._juger,
                                        "claude-sonnet-5-5", "claude-sonnet-5-5")
        with self.assertRaises(ValueError):
            runner.verifier_juge_different("claude-sonnet-5-5", "")

    def test_rapport_porte_cout_par_question(self):
        import json
        import tempfile
        rapport = runner.run_eval_commerciaux(
            self._repondre, self._juger, "claude-sonnet-5-5", "claude-haiku-5-5")
        self.assertEqual(rapport["total"], 50)
        self.assertEqual(rapport["taux"], 1.0)
        # 1000*0.10 + 200*2 + 100*10 = 1500 USD/MTok-tokens -> 0.0015 USD
        self.assertAlmostEqual(rapport["questions"][0]["cout_usd"], 0.0015)
        self.assertAlmostEqual(rapport["cout_usd_par_question"], 0.0015)
        self.assertEqual(set(rapport["par_intention"]), {
            "question_manuel", "donnee", "action", "bug", "manque", "hors_champ"})
        with tempfile.TemporaryDirectory() as dossier:
            chemin = runner.ecrire_rapport(rapport, dossier=dossier)
            with open(chemin, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["total"], 50)

    def test_mauvais_outil_ou_juge_negatif_fait_echouer(self):
        def sans_outil(case):
            return {"answer": "", "tokens": {}}

        rapport = runner.run_eval_commerciaux(
            sans_outil, self._juger, "claude-sonnet-5-5", "claude-haiku-5-5")
        echecs = {q["id"] for q in rapport["questions"] if not q["passed"]}
        from tests.eval.cases_commerciaux import CASES_COMMERCIAUX
        attendus = {c["id"] for c in CASES_COMMERCIAUX if c["outil"]}
        self.assertEqual(echecs, attendus)


if __name__ == "__main__":
    unittest.main()
