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

    def test_somme_des_lignes_de_devis_signalee(self):
        """AANA81 (C-AANA-VER4-032) — le montant d'un devis par somme de ses
        lignes est signale ; le prompt ne la prescrit plus."""
        case = next(c for c in CASES if c["id"] == "somme_lignes_devis_accepte")
        result = runner.score_case(case)
        self.assertTrue(result["passed"])
        self.assertIn("somme des lignes de devis", result["reason"])
        self.assertNotIn("SUM(ventes_lignedevis", runner.svc._AGENT_PREFIX)
        self.assertIn("fiche ERP", runner.svc._AGENT_PREFIX)
        self.assertIn("total_ht_stocke", runner.svc._AGENT_PREFIX)
        listing = next(c for c in CASES if c["id"] == "join_devis_lignes")
        self.assertTrue(runner.score_case(listing)["passed"])

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
            from app.services.action_tools import ActionContext
            from app.services.relais_copilote import lire_appelant
            ctx = ActionContext(
                company_id=int(os.environ.get("ASSISTANT_EVAL_COMPANY_ID", "1")),
                role="normal", permissions=[], token=jeton, is_superuser=False)
            lire_appelant(ctx)  # COP-B2 : permissions + prenom/role (en-tete)
        repondre = runner.repondeur_reel(
            int(os.environ.get("ASSISTANT_EVAL_COMPANY_ID", "1")),
            int(os.environ.get("ASSISTANT_EVAL_USER_ID", "1")), ctx)
        rapport = runner.run_eval_commerciaux(repondre, runner.juge_reel(juge), modele, juge)
        self.assertTrue(os.path.exists(runner.ecrire_rapport(rapport)))
        # COP-B7 — scenarios du copilote (exigent le jeton : outils d'action).
        if ctx is not None:
            from tests.eval.cases_commerciaux import CASES_COPILOTE
            copilote = runner.run_eval_commerciaux(
                repondre, runner.juge_reel(juge), modele, juge, cases=CASES_COPILOTE)
            self.assertTrue(os.path.exists(runner.ecrire_rapport(
                copilote, nom=f"copilote_{modele}.json")))
            # TCH116 — et les douze conversations du Copilote sur les tâches.
            from tests.eval.cases_commerciaux import CASES_COACH
            coach = runner.run_eval_commerciaux(
                repondre, runner.juge_reel(juge), modele, juge, cases=CASES_COACH)
            self.assertTrue(os.path.exists(runner.ecrire_rapport(coach, nom=f"coach_{modele}.json")))
            # Copilote vague 2 (TXT5) — scenarios par domaine (moteur natif, copilote allume).
            from tests.eval.cases_vague2 import CASES_VAGUE2
            vague2 = runner.run_eval_commerciaux(
                repondre, runner.juge_reel(juge), modele, juge, cases=CASES_VAGUE2)
            self.assertTrue(os.path.exists(runner.ecrire_rapport(vague2, nom=f"vague2_{modele}.json")))
            # D-COP-5 (21/11/2026) — quinze questions simples : reponse directe d'abord.
            from tests.eval.cases_simples import CASES_SIMPLES
            simples = runner.run_eval_commerciaux(
                repondre, runner.juge_reel(juge), modele, juge, cases=CASES_SIMPLES)
            self.assertTrue(os.path.exists(runner.ecrire_rapport(simples, nom=f"simples_{modele}.json")))


class EvalCommerciauxTests(unittest.TestCase):
    """AIC10 — jeu de 50 questions de commerciaux, fournisseur SIMULE (aucun
    appel payant) ; le rejeu reel exige ASSISTANT_EVAL=1 + une cle."""

    @staticmethod
    def _repondre(case):
        """Reponse ideale A LA FORME DU SERVICE : `sql_query` toujours vide
        (ERR84), outils lus dans `outils_appeles`, ecritures en propositions."""
        appeles = runner.outils_requis(case) + list(case.get("un_parmi") or ())[:1]
        return {"answer": "ok", "outils_appeles": appeles, "sql_query": "",
                "cartes": [{"type": "proposition", "action_key": cle}
                           for cle in case.get("a_confirmer") or () if cle in appeles]
                + [{"type": "resultat", "action_key": cle, "carte": "tache",
                    "donnees": {"proposition": {"geste": "ecrire", "action_key": cle}}}
                   for cle in case.get("a_valider") or () if cle in appeles]
                + [{"type": "resultat", "carte": carte} for carte in case.get("cartes") or ()],
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
        attendus = {c["id"] for c in CASES_COMMERCIAUX
                    if runner.outils_requis(c) or c.get("un_parmi")}
        self.assertEqual(echecs, attendus)

    def test_attentes_reparees_sql_et_signalement(self):
        """COP-B7 — un cas `sql_db_query` ou `report_gap` passe quand l'outil
        est dans `outils_appeles` (forme reelle : `sql_query` vide). Avant,
        12 cas sur 50 etaient impossibles."""
        from tests.eval.cases_commerciaux import CASES_COMMERCIAUX
        cas = [c for c in CASES_COMMERCIAUX if c["outil"] in ("sql_db_query", "report_gap")]
        self.assertEqual(len(cas), 12)
        rapport = runner.run_eval_commerciaux(
            self._repondre, self._juger, "claude-sonnet-5-5", "claude-haiku-5-5", cases=cas)
        self.assertEqual(rapport["reussis"], 12)

    def test_scenarios_du_copilote(self):
        """COP-B7 — 15 phrases du jour + 2 injections + 2 darija + 4 demandes de
        devis (copilote v2) ; chaque cle attendue ou interdite est connue ;
        chaque scenario attend un outil ou interdit une ecriture ; la reponse
        ideale passe a 100 %."""
        from tests.eval.cases_commerciaux import CASES_COPILOTE, CLES_COPILOTE
        sources = [c["source"] for c in CASES_COPILOTE]
        self.assertEqual((sources.count("voix"), sources.count("injection"),
                          sources.count("darija"), sources.count("devis"), len(CASES_COPILOTE)),
                         (15, 2, 2, 4, 23))
        self.assertEqual(len({c["id"] for c in CASES_COPILOTE}), 23)
        devis = {c["id"]: c for c in CASES_COPILOTE if c["source"] == "devis"}
        self.assertEqual(runner.outils_requis(devis["dev_demande_client_nomme"]),
                         ["crm.lead.chercher", "ventes.catalogue.chercher", "ventes.devis.composer"])
        self.assertIn("ventes.devis.composer", devis["dev_demande_sans_client"]["interdits"])
        self.assertEqual(devis["dev_demande_depuis_taches"]["contexte"]["ecran"], "/taches/aujourdhui")
        self.assertEqual(devis["dev_whatsapp_colle"]["a_confirmer"], ("crm.lead.creer",))
        self.assertTrue(all(c.get("interdits") for c in devis.values()))
        for c in CASES_COPILOTE:
            cles = set(runner.outils_requis(c)) | set(c.get("un_parmi") or ()) \
                | set(c.get("interdits") or ()) | set(c.get("a_confirmer") or ())
            self.assertTrue(cles, c["id"])
            self.assertLessEqual(cles, CLES_COPILOTE, c["id"])
            self.assertFalse(set(c.get("interdits") or ()) & set(runner.outils_requis(c)))
        self.assertTrue(all(c.get("interdits") for c in CASES_COPILOTE
                            if c["source"] == "injection"))
        rapport = runner.run_eval_commerciaux(
            self._repondre, self._juger, "claude-sonnet-5-5", "claude-haiku-5-5",
            cases=CASES_COPILOTE)
        self.assertEqual(rapport["taux"], 1.0, [q for q in rapport["questions"] if q["echecs"]])

    def test_scenarios_du_coach(self):
        """TCH116 — les dix-sept conversations de textes.md §5.8 (douze, puis
        les cinq qui manquaient), plus celles de la revue F3 (A5), du Copilote sur les tâches, APRÈS
        celles du copilote (23 depuis le copilote v2) : ids uniques, clés connues, injections
        avec interdits, une carte attendue sauf hors sujet ; la réponse idéale
        passe à 100 %, une carte manquante échoue en `bonne_carte`."""
        from tests.eval.cases_commerciaux import CASES_COACH, CASES_COPILOTE, CLES_COACH
        self.assertEqual((len(CASES_COACH), len(CASES_COPILOTE)), (19, 23))
        ids = [c["id"] for c in CASES_COACH]
        self.assertEqual(len(set(ids)), 19)
        self.assertLessEqual({"coa_ou_j_en_suis", "coa_modifier", "coa_plus_sept",
                              "inj_modifier_tiers", "groq_plus", "inj_journee_lead",
                              "inj_liste_puis_ok"}, set(ids))
        from app.services.relais_copilote import question_porte_un_texte_tiers
        for c in CASES_COACH:
            self.assertTrue(all(question_porte_un_texte_tiers(q) for q in c.get("avant") or ()), c["id"])
        self.assertFalse(set(ids) & {c["id"] for c in CASES_COPILOTE})
        for c in CASES_COACH:
            cles = set(runner.outils_requis(c)) | set(c.get("un_parmi") or ()) \
                | set(c.get("interdits") or ()) | set(c.get("a_valider") or ())
            self.assertTrue(cles, c["id"])
            self.assertLessEqual(cles, CLES_COACH, c["id"])
            self.assertFalse(set(c.get("interdits") or ()) & set(runner.outils_requis(c)))
            self.assertFalse(set(c.get("interdits") or ()) & set(c.get("a_valider") or ()), c["id"])
            self.assertEqual(bool(c.get("cartes")), c["id"] != "coa_hors_sujet_devis", c["id"])
        self.assertTrue(all(c.get("interdits") for c in CASES_COACH if c["source"] == "injection"))
        rapport = runner.run_eval_commerciaux(
            self._repondre, self._juger, "claude-sonnet-5-5", "claude-haiku-5-5", cases=CASES_COACH)
        self.assertEqual(rapport["taux"], 1.0, [q for q in rapport["questions"] if q["echecs"]])

        def sans_carte(case):
            return {**self._repondre(case), "cartes": []}
        prioriser = next(c for c in CASES_COACH if c["id"] == "coa_prioriser")
        rapport = runner.run_eval_commerciaux(
            sans_carte, self._juger, "claude-sonnet-5-5", "claude-haiku-5-5", cases=[prioriser])
        self.assertEqual(rapport["questions"][0]["echecs"], ["bonne_carte"])

    def test_scenarios_vague2(self):
        """Copilote vague 2 (TXT5) — un jeu par domaine charge + deux travaux en
        etapes : totaux par domaine, ids uniques et distincts des autres jeux ;
        la reponse ideale passe a 100 %."""
        from tests.eval.cases_commerciaux import CASES_COACH, CASES_COPILOTE
        from tests.eval.cases_vague2 import CASES_PAR_DOMAINE, CASES_VAGUE2
        self.assertEqual({d: len(c) for d, c in CASES_PAR_DOMAINE.items()}, {
            "calepinage": 6, "visites": 7, "installations": 6, "ventes": 14, "stock": 6,
            "sav": 7, "reporting": 4, "travail": 8})
        ids = [c["id"] for c in CASES_VAGUE2]
        self.assertEqual(len(set(ids)), 58)
        self.assertFalse(set(ids) & {c["id"] for c in CASES_COPILOTE + CASES_COACH})
        rapport = runner.run_eval_commerciaux(
            self._repondre, self._juger, "claude-sonnet-5-5", "claude-haiku-5-5", cases=CASES_VAGUE2)
        self.assertEqual(rapport["taux"], 1.0, [q for q in rapport["questions"] if q["echecs"]])

    def test_format_des_scenarios_vague2(self):
        """TXT5 — chaque cas ne cite que des cles du vocabulaire ferme ; toute
        ecriture attendue non silencieuse est dans `a_confirmer` ; une injection
        porte son texte piege et ses interdits ; un levier nomme son champ ;
        chaque domaine a ses familles (sauf absence declaree) ; chaque domaine a
        consignes a ses scenarios."""
        from app.services import chargeur_outils, consignes_domaines
        from tests.eval import cases_vague2 as v2
        self.assertEqual(v2.SILENCIEUSES, {"calepinage.simuler", "sav.ticket.noter", "crm.lead.note",
                                           "ventes.devis.composer", "ventes.devis.creer_auto"})
        self.assertLessEqual(set(v2.CLES_VAGUE2.values()), set(v2.GENRES))
        for cle, genre in v2.CLES_VAGUE2.items():
            self.assertEqual(genre == "silencieuse", cle in v2.SILENCIEUSES, cle)
            if genre != "outil_fixe":
                self.assertIn(cle.split(".")[0], chargeur_outils.DOMAINES + ("erp",), cle)
        for c in v2.CASES_VAGUE2:
            with self.subTest(cas=c["id"]):
                attendus = set(runner.outils_requis(c)) | set(c.get("un_parmi") or ())
                cites = attendus | set(c.get("interdits") or ()) | set(c.get("a_confirmer") or ())
                self.assertTrue(cites)
                self.assertLessEqual(cites, set(v2.CLES_VAGUE2))
                self.assertFalse(set(c.get("interdits") or ()) & attendus)
                self.assertLessEqual({k for k in attendus if v2.CLES_VAGUE2[k] == "confirmee"},
                                     set(c.get("a_confirmer") or ()))
                # D-COP-5 : `a_confirmer` = cartes ; une cle `directe` n'y figure que si la
                # question porte un texte colle (`texte_colle`), sinon le geste est execute.
                genres_carte = {v2.CLES_VAGUE2[k] for k in c.get("a_confirmer") or ()}
                self.assertLessEqual(genres_carte, {"confirmee", "directe"})
                if "directe" in genres_carte:
                    self.assertTrue(c.get("texte_colle"), c["id"])
                if c.get("texte_colle"):
                    from app.services.relais_copilote import question_porte_un_texte_tiers
                    self.assertTrue(question_porte_un_texte_tiers(c["question"]), c["id"])
                self.assertIn(c["famille"], v2.FAMILLES)
                self.assertEqual(c["source"], "vague2")
                if c["famille"] == "injection":
                    self.assertTrue(c.get("interdits") and c.get("donnees_piegees"))
                self.assertEqual(c["famille"] == "levier", bool(c.get("leviers")))
                self.assertLessEqual(set(c.get("leviers") or ()), set(v2.LEVIERS))
                self.assertEqual(c["famille"] == "etape", c["domaine"] == "travail")
                for question in c.get("avant") or ():
                    self.assertIsInstance(question, str)
        for domaine, cas in v2.CASES_PAR_DOMAINE.items():
            if domaine == "travail":
                continue
            familles = {c["famille"] for c in cas}
            absentes = set(v2.FAMILLES_ABSENTES.get(domaine, ()))
            self.assertEqual(familles, set(v2.FAMILLES) - {"etape"} - absentes, domaine)
            self.assertTrue(all(c["domaine"] == domaine for c in cas), domaine)
        self.assertLessEqual(set(consignes_domaines.CONSIGNES), set(v2.CASES_PAR_DOMAINE))

    @staticmethod
    def _cles_du_registre():
        """Cles `key='...'` des agent_actions.py + registre Django, lues comme TEXTE
        (l'environnement FastAPI n'a pas Django) ; None si le depot Django est absent."""
        import glob
        import re
        racine = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "django_core", "apps")
        fichiers = glob.glob(os.path.join(racine, "*", "agent_actions.py"))
        fichiers += glob.glob(os.path.join(racine, "agent", "registry.py"))
        if not fichiers:
            return None
        cles = {"report_gap", "sql_db_query", "erp.ouvrir"}
        for f in fichiers:
            with open(f, encoding="utf-8") as fh:
                cles |= set(re.findall(r"key=['\"]([a-z_.]+)['\"]", fh.read()))
        return cles

    def test_directes_alignees_sur_le_registre(self):
        """D-COP-5 (21/11/2026) — les cles `directe` du vocabulaire = ACTIONS_DIRECTES du
        registre Django (lu en AST) ; `a_confirmer` ne cite que des cartes (ou un texte colle) ;
        les 15 questions simples existent, ne citent que des cles du registre et n'ecrivent rien."""
        import ast
        from tests.eval import cases_simples as simples
        from tests.eval import cases_vague2 as v2
        chemin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "django_core", "apps", "agent", "registry.py")
        self.assertEqual({k for k, g in v2.CLES_VAGUE2.items() if g == "directe"}, set(v2.DIRECTES))
        self.assertFalse(v2.DIRECTES & set(v2.SILENCIEUSES))
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as fh:
                arbre = ast.parse(fh.read())
            registre = next(frozenset(ast.literal_eval(n.value.args[0])) for n in ast.walk(arbre)
                            if isinstance(n, ast.Assign)
                            and any(getattr(t, "id", "") == "ACTIONS_DIRECTES" for t in n.targets))
            self.assertEqual(registre - v2.DIRECTES_A_VENIR, v2.DIRECTES_REGISTRE)
            self.assertLessEqual(registre, v2.DIRECTES)
        cles = self._cles_du_registre()
        if cles is not None:
            self.assertLessEqual(v2.DIRECTES, cles)
            for c in v2.CASES_VAGUE2 + simples.CASES_SIMPLES:
                cites = set(runner.outils_requis(c)) | set(c.get("un_parmi") or ())
                cites |= set(c.get("interdits") or ()) | set(c.get("a_confirmer") or ())
                self.assertLessEqual(cites, cles, c["id"])
        self.assertEqual(len(simples.CASES_SIMPLES), 15)
        self.assertEqual(len({c["id"] for c in simples.CASES_SIMPLES}), 15)
        for c in simples.CASES_SIMPLES:
            self.assertEqual((c["source"], c.get("reponse_courte")), ("simple", True))
            self.assertFalse(c.get("a_confirmer"), c["id"])
            self.assertTrue(c.get("interdits"), c["id"])
        rapport = runner.run_eval_commerciaux(
            self._repondre, self._juger, "claude-sonnet-5-5", "claude-haiku-5-5",
            cases=simples.CASES_SIMPLES)
        self.assertEqual(rapport["taux"], 1.0, [q for q in rapport["questions"] if q["echecs"]])

    def test_ecriture_sans_carte_ou_interdite_fait_echouer(self):
        from tests.eval.cases_commerciaux import CASES_COPILOTE
        signe = next(c for c in CASES_COPILOTE if c["id"] == "dev_whatsapp_colle")
        piege = next(c for c in CASES_COPILOTE if c["id"] == "inj_note_remise")

        def execute_sans_carte(case):
            rep = self._repondre(case)
            rep["cartes"] = [{"type": "resultat", "action_key": "crm.lead.creer"}]
            return rep

        def obeit_a_la_note(case):
            rep = self._repondre(case)
            rep["outils_appeles"] = rep["outils_appeles"] + ["ventes.devis.remise"]
            return rep
        for repondre, cas in ((execute_sans_carte, signe), (obeit_a_la_note, piege)):
            rapport = runner.run_eval_commerciaux(
                repondre, self._juger, "claude-sonnet-5-5", "claude-haiku-5-5", cases=[cas])
            self.assertEqual(rapport["questions"][0]["echecs"], ["ecriture_sans_carte"])

    def test_ecriture_taches_faite_au_lieu_d_une_carte_echo_fait_echouer(self):
        """A5 (revue F3) — `a_valider` : une carte sans `proposition` (écriture faite) ou une écriture
        appelée sans aucune carte échoue en `ecriture_sans_carte`."""
        from tests.eval.cases_commerciaux import CASES_COACH
        modifier = next(c for c in CASES_COACH if c["id"] == "coa_modifier")

        def ecrite(case):
            rep = self._repondre(case)
            rep["cartes"] = [c if c.get("action_key") != "taches.tache.modifier"
                             else {**c, "donnees": {"tache": {"id": 21}}} for c in rep["cartes"]]
            return rep

        def sans_carte(case):
            rep = self._repondre(case)
            rep["cartes"] = [c for c in rep["cartes"] if c.get("action_key") != "taches.tache.modifier"]
            return rep
        for repondre in (ecrite, sans_carte):
            rapport = runner.run_eval_commerciaux(
                repondre, self._juger, "claude-sonnet-5-5", "claude-haiku-5-5", cases=[modifier])
            self.assertEqual(rapport["questions"][0]["echecs"], ["ecriture_sans_carte"])

    def test_cout_compte_les_ecritures_de_cache(self):
        """COP-B4/B7 — une ecriture de cache 1 h coute 2x l'entree."""
        self.assertAlmostEqual(runner.cout_usd({"cache_write": 1_000_000},
                                               "claude-sonnet-5-5"), 4.0)


if __name__ == "__main__":
    unittest.main()
