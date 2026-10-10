"""Tests de scripts/check_acceptation.py (garde d'acceptation, AMET88).

Stdlib pur (unittest), aucun Django, aucune base, aucun docker, aucun reseau.
Depot jetable dans un dossier temporaire ; ``git init`` seulement pour les
tests de la base git (dette qui grossit). Lancer :
    python -m unittest scripts.tests.test_check_acceptation -v
"""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_acceptation as cacc  # noqa: E402

PLAN = "docs/plans/PLAN_AUDIT_TEST.md"
SHA = "abcdef1234567890abcdef1234567890abcdef12"


def ligne(etat, ident, preuve="P1.1 — devis envoye, ecran relu"):
    return (f"- [{etat}] {ident} — **Une tache** : Given x When y Then z. "
            f"Preuve en direct : {preuve}. Hors périmètre : rien. "
            f"Files: `backend/x.py` (@model: sonnet)\n")


def etape(ident="P1.1", taches=("ATST1",), verdict="PASS", base=None, **autres):
    e = {"id": ident, "taches": list(taches), "verdict": verdict,
         "base_verdict": base, "trace": "traces/p1.1.zip",
         "oracles": {str(i): "PASS" if i < 5 else "NA" for i in range(1, 11)}}
    e.update(autres)
    return e


class FauxDepot:
    """Depot jetable : un plan d'audit + docs/audits/acceptation/."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        (self.racine / "docs" / "plans").mkdir(parents=True)
        self._sauvegarde = cacc.ROOT
        cacc.ROOT = self.racine

    def plan(self, *lignes):
        (self.racine / PLAN).write_text("# Plan\n" + "".join(lignes), encoding="utf-8")

    def enregistrement(self, groupe="ATST", couvre=("ATST1",), etapes=None,
                       verdict="PASS", ecart=(), sans_json=False, tete=None):
        etapes = [etape()] if etapes is None else etapes
        dossier = self.racine / cacc.DOSSIER / groupe
        dossier.mkdir(parents=True, exist_ok=True)
        nom = f"2026-10-09-{SHA[:9]}"
        res = {"sha": SHA, "date": "2026-10-09", "groupe": groupe, "verdict": verdict,
               "couvre": list(couvre), "couvre_avec_ecart": list(ecart), "etapes": etapes}
        if not sans_json:
            (dossier / f"{nom}.results.json").write_text(json.dumps(res), encoding="utf-8")
        lignes_etapes = "".join(
            f"  - id: {e.get('id')}\n    tache: [{', '.join(e.get('taches') or [])}]\n"
            f"    verdict: {e.get('verdict')}\n" for e in etapes)
        texte = tete if tete is not None else (
            f"---\nsha: {SHA}\ndate: 2026-10-09\ngroupe: {groupe}\n"
            f"couvre: [{', '.join(couvre)}]\ncouvre_avec_ecart: [{', '.join(ecart)}]\n"
            f"verdict: {verdict}\netapes:\n{lignes_etapes}---\n\n# Acceptation {groupe}\n")
        (dossier / f"{nom}.md").write_text(texte, encoding="utf-8")

    def dette(self, groupe, *ids):
        cacc.ecrire_dette(groupe, set(ids), "0000000aa")

    def git(self, *args):
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                       cwd=self.racine, check=True, capture_output=True)

    def commit_base(self):
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.racine, check=True,
                              capture_output=True, text=True).stdout.strip()

    def close(self):
        cacc.ROOT = self._sauvegarde
        self.tmp.cleanup()


class AcceptationTests(unittest.TestCase):
    def setUp(self):
        self.depot = FauxDepot()
        self.addCleanup(self.depot.close)

    def lancer(self, *args):
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            code = cacc.main(list(args) or ["--base", "AUCUNE-BASE"])
        return code, sortie.getvalue()

    # -- la regle -------------------------------------------------------------
    def test_tache_cochee_sans_enregistrement_ni_dette_echoue(self):
        self.depot.plan(ligne("x", "ATST1"))
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("ATST1", sortie)
        self.assertIn("ni couverte", sortie)

    def test_tache_couverte_par_enregistrement_pass_passe(self):
        self.depot.plan(ligne("x", "ATST1"), ligne(" ", "ATST2"))
        self.depot.enregistrement()
        code, sortie = self.lancer()
        self.assertEqual(code, 0, sortie)
        self.assertIn("ATST : 1 cochée(s) à preuve, 1 couverte(s), 0 en dette", sortie)

    def test_tache_en_dette_passe(self):
        self.depot.plan(ligne("x", "ATST1"))
        self.depot.dette("ATST", "ATST1")
        code, sortie = self.lancer()
        self.assertEqual(code, 0, sortie)

    def test_tag_cite_entre_backticks_ne_compte_pas(self):
        # AMET89 : une tache qui PARLE du tag (`(@acceptation)`) n'est pas une acceptation.
        self.depot.plan("- [x] ATST1 — **plan_lanes : tag `(@acceptation)` reconnu** : Given x "
                        "When y Then z. Preuve en direct : n/a — planner. Files: `s.py`\n",
                        "- [x] ATST2 — **Acceptation du groupe** : Given x When y Then z. "
                        "Preuve en direct : n/a. Files: `s.py` (@acceptation)\n")
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("ATST2", sortie)
        self.assertNotIn("ATST1 (", sortie)

    def test_groupe_accepte_seulement_si_tout_couvert_sans_dette(self):
        # AMET91 lit `--groupe G` : 0 = accepte (tout couvert, dette vide), 1 sinon.
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "ATST2"))
        self.depot.enregistrement(couvre=("ATST1",))
        code, sortie = self.lancer("--groupe", "ATST")
        self.assertEqual(code, 1, sortie)
        self.assertIn("1 non couverte(s)", sortie)
        self.depot.dette("ATST", "ATST2")
        code, sortie = self.lancer("--groupe", "atst")
        self.assertEqual(code, 1, sortie)  # en dette = pas encore accepte
        self.depot.enregistrement(couvre=("ATST1", "ATST2"),
                                  etapes=[etape(), etape("P1.2", ("ATST2",))])
        self.depot.dette("ATST")
        code, sortie = self.lancer("--groupe", "ATST")
        self.assertEqual(code, 0, sortie)

    def test_preuves_qui_ne_comptent_pas_et_tags_qui_comptent(self):
        self.depot.plan(ligne("x", "ATST1", "n/a — garde CI (PA4.3 ailleurs)"),
                        ligne("x", "ATST2", "API seulement — le rejeu PA4.3 est porté ailleurs"),
                        ligne("x", "ATST3", "pile locale — sans etape"),
                        ligne("x", "ATST4", "n/a — orchestrateur (@acceptation)"),
                        ligne("x", "ATST5", "rejeu de PA3 étape 2"))
        self.assertEqual(sorted(cacc.taches_a_preuve()), ["ATST4", "ATST5"])

    def test_enregistrement_fail_ne_couvre_pas(self):
        self.depot.plan(ligne("x", "ATST1"))
        self.depot.enregistrement(verdict="FAIL", etapes=[etape(verdict="FAIL")])
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("ni couverte", sortie)

    # -- enregistrements non conformes ------------------------------------------
    def test_enregistrement_sans_results_json_echoue(self):
        self.depot.plan(ligne("x", "ATST1"))
        self.depot.enregistrement(sans_json=True)
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("results.json absent", sortie)

    def test_etape_vide_echoue(self):
        self.depot.plan(ligne("x", "ATST1"))
        self.depot.enregistrement(etapes=[etape(), etape("P1.2", oracles={})])
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("étape 2 vide ou incomplète", sortie)

    def test_en_tete_different_du_results_json_echoue(self):
        self.depot.plan(ligne("x", "ATST1"))
        self.depot.enregistrement(tete=f"---\nsha: {SHA}\ndate: 2026-10-09\ngroupe: ATST\n"
                                       "couvre: [ATST9]\nverdict: PASS\netapes:\n"
                                       "  - id: P1.1\n    tache: ATST1\n    verdict: PASS\n---\n")
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("en-tête `couvre`", sortie)

    def test_couvre_avec_ecart_admis_si_l_etape_echoue_aussi_a_la_base(self):
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "ATST2"))
        self.depot.enregistrement(couvre=("ATST1", "ATST2"), ecart=("ATST2",), etapes=[
            etape(), etape("P1.2", ("ATST2",), verdict="FAIL", base="FAIL")])
        code, sortie = self.lancer()
        self.assertEqual(code, 0, sortie)

    def test_couvre_avec_ecart_refuse_si_la_base_passe(self):
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "ATST2"))
        self.depot.enregistrement(couvre=("ATST1", "ATST2"), ecart=("ATST2",), etapes=[
            etape(), etape("P1.2", ("ATST2",), verdict="FAIL", base="PASS")])
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("échoue aussi à la base", sortie)

    # -- la dette ne fait que retrecir ----------------------------------------
    def test_seule_une_coche_apportee_par_la_pr_est_reprochee(self):
        # File de merge : une tâche DÉJÀ cochée sur la base (mergée par une autre PR) n'est
        # jamais reprochée à cette PR (avis) ; une coche APPORTÉE par la PR l'est.
        self.depot.plan(ligne("x", "ATST1"), ligne(" ", "ATST2"))
        base = self.depot.commit_base()
        code, sortie = self.lancer("--base", base)
        self.assertEqual(code, 0, sortie)
        self.assertIn("ATST1", sortie)
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "ATST2"))
        code, sortie = self.lancer("--base", base)
        self.assertEqual(code, 1, sortie)
        self.assertIn("ATST2 (", sortie)
        self.assertNotIn("ATST1 (", sortie)

    def test_dette_qui_grossit_echoue(self):
        """Mutant : accepter une dette qui grossit ⇒ la garde DOIT echouer."""
        self.depot.plan(ligne("x", "ATST1"), ligne(" ", "ATST2"))
        self.depot.dette("ATST", "ATST1")
        base = self.depot.commit_base()
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "ATST2"))
        self.depot.dette("ATST", "ATST1", "ATST2")
        code, sortie = self.lancer("--base", base)
        self.assertEqual(code, 1, sortie)
        self.assertIn("a GROSSI", sortie)
        self.assertIn("ATST2", sortie)

    def test_nouvelle_dette_apres_la_bascule_echoue(self):
        self.depot.plan(ligne("x", "ATST1"), ligne(" ", "AUTR1"))
        self.depot.dette("ATST", "ATST1")
        base = self.depot.commit_base()
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "AUTR1"))
        self.depot.dette("AUTR", "AUTR1")
        code, sortie = self.lancer("--base", base)
        self.assertEqual(code, 1, sortie)
        self.assertIn("AUTR1", sortie)

    def test_dette_amorcee_a_la_bascule_et_qui_retrecit_passe(self):
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "ATST2"))
        base = self.depot.commit_base()
        self.depot.dette("ATST", "ATST1", "ATST2")
        code, sortie = self.lancer("--base", base)
        self.assertEqual(code, 0, sortie)
        self.depot.git("add", "-A")
        self.depot.git("commit", "-q", "-m", "bascule")
        self.depot.enregistrement(couvre=("ATST2",), etapes=[etape(taches=("ATST2",))])
        self.depot.dette("ATST", "ATST1")
        code, sortie = self.lancer("--base", "HEAD")
        self.assertEqual(code, 0, sortie)

    def test_dette_perimee_echoue_puis_write_baseline_retrecit(self):
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "ATST2"))
        self.depot.dette("ATST", "ATST1", "ATST2")
        self.depot.enregistrement()
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("--write-baseline", sortie)
        self.assertEqual(self.lancer("--write-baseline")[0], 0)
        self.assertEqual(cacc.dettes()["ATST"], {"ATST2"})
        self.assertEqual(self.lancer()[0], 0)

    def test_id_archive_reste_en_dette_sans_bloquer_ni_etre_efface(self):
        """« clean the plans » déplace `- [x] ATST2` vers docs/done_task.md : jamais rejouée, elle
        reste en dette (ni « périmée », ni effacée par --write-baseline). Seuls un id COUVERT ou un id
        encore présent mais plus coché à preuve (ATST3) font rétrécir la dette."""
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "ATST2"), ligne("x", "ATST3"), ligne("x", "ATST4"))
        self.depot.dette("ATST", "ATST1", "ATST2", "ATST3", "ATST4")
        self.depot.enregistrement(couvre=("ATST4",), etapes=[etape(taches=("ATST4",))])
        self.depot.plan(ligne("x", "ATST1"), ligne(" ", "ATST3"))  # ATST2 et ATST4 archivées
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("dette ATST : 2 id(s) couvert(s) ou plus cochés à preuve (ATST3, ATST4)", sortie)
        self.assertEqual(self.lancer("--write-baseline")[0], 0)
        self.assertEqual(cacc.dettes()["ATST"], {"ATST1", "ATST2"})
        self.assertEqual(self.lancer()[0], 0)

    def test_amorcer_une_seule_fois_par_groupe(self):
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "ATST2"), ligne(" ", "ATST3"))
        self.depot.enregistrement()
        self.lancer("--amorcer")
        self.assertEqual(cacc.dettes(), {"ATST": {"ATST2"}})
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "ATST2"), ligne("x", "ATST3"))
        _code, sortie = self.lancer("--amorcer")
        self.assertIn("déjà amorcée", sortie)
        self.assertEqual(cacc.dettes(), {"ATST": {"ATST2"}})

    def test_rapport_ne_bloque_jamais(self):
        self.depot.plan(ligne("x", "ATST1"))
        code, sortie = self.lancer("--rapport", "--base", "AUCUNE-BASE")
        self.assertEqual(code, 0, sortie)
        self.assertIn("ATST1", sortie)

    # -- AMET90 : l'enregistrement tel que l'ecrit la spec exemple ---------------
    def ecrire_exemple_adep(self, vider_etape=None):
        """Paire .md / .results.json ecrite A LA MAIN dans la forme EXACTE de
        frontend/e2e/acceptation/_enregistrement.js (spec adep.spec.js)."""
        self.depot.plan(*(ligne("x", i, "P5.1 — Playwright sur la pile locale")
                          for i in ("ADEP16", "ADEP17", "ADEP18", "ADEP19", "ADEP99")),
                        ligne("x", "ACHT69", "P4.2 — compte terrain, lot refuse"))
        sha = "189c655e0" + "a" * 31
        oracles = {str(i): "NA" for i in range(1, 11)}
        oracles.update({"1": "PASS", "2": "PASS", "3": "PASS", "4": "PASS", "8": "PASS"})
        pas = [("P5.1", ["ADEP16", "ADEP17", "ADEP99"]), ("P5.2", ["ADEP16", "ADEP99"]),
               ("P5.3", ["ADEP18", "ACHT69", "ADEP99"]), ("P5.3-500", ["ACHT69", "ADEP99"]),
               ("P5.4", ["ADEP19", "ADEP99"])]
        etapes = [{"id": i, "taches": t, "verdict": "PASS", "base_verdict": None,
                   "trace": f"docs/qa-explorer/captures/2026-10-10/ACCEPTATION-ADEP-{i}.jpg",
                   "oracles": dict(oracles, **({"5": "PASS"} if i in ("P5.1", "P5.2") else {})),
                   "notes": ""} for i, t in pas]
        if vider_etape is not None:
            etapes[vider_etape].update(oracles={}, trace="")
        couvre = ["ADEP16", "ADEP17", "ADEP18", "ADEP19", "ACHT69", "ADEP99"]
        res = {"sha": sha, "date": "2026-10-10", "groupe": "ADEP", "verdict": "PASS",
               "couvre": couvre, "couvre_avec_ecart": [], "etapes": etapes}
        dossier = self.depot.racine / cacc.DOSSIER / "ADEP"
        dossier.mkdir(parents=True)
        nom = "2026-10-10-189c655e0"
        (dossier / f"{nom}.results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
        tete = "".join(f"  - id: {i}\n    tache: [{', '.join(t)}]\n    verdict: PASS\n"
                       for i, t in pas)
        (dossier / f"{nom}.md").write_text(
            f"---\nsha: {sha}\ndate: 2026-10-10\ngroupe: ADEP\ncouvre: [{', '.join(couvre)}]\n"
            f"couvre_avec_ecart: []\nverdict: PASS\netapes:\n{tete}---\n\n"
            "# Acceptation ADEP — 2026-10-10 (189c655e0)\n\n"
            "| Étape | Tâches | Verdict | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Trace |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
            "| P5.1 | ADEP16, ADEP17, ADEP99 | PASS | PASS | PASS | PASS | PASS | PASS | NA | NA "
            "| PASS | NA | NA | docs/qa-explorer/captures/2026-10-10/ACCEPTATION-ADEP-P5.1.jpg |\n",
            encoding="utf-8")

    def test_enregistrement_produit_par_la_spec_exemple_est_pass(self):
        self.ecrire_exemple_adep()
        code, sortie = self.lancer()
        self.assertEqual(code, 0, sortie)
        self.assertIn("ADEP : 5 cochée(s) à preuve, 5 couverte(s), 0 en dette", sortie)
        self.assertIn("ACHT : 1 cochée(s) à preuve, 1 couverte(s), 0 en dette", sortie)

    def test_ecart_accepte_tel_que_l_ecrit_la_spec_est_pass_et_refuse_sans_base_fail(self):
        """Forme de `_enregistrement.js::composer` pour une étape `{ ecart }` (P1.13 d'ADEP) :
        corps vert, oracle 3 FAIL, base_verdict FAIL, tâche dans couvre ET couvre_avec_ecart."""
        self.depot.plan(ligne("x", "ATST1"), ligne("x", "ATST2"))
        oracles = dict(etape()["oracles"], **{"3": "FAIL"})
        ecart = etape("P1.13", ("ATST2",), verdict="FAIL", base="FAIL", oracles=oracles,
                      notes="écart accepté (base FAIL) : défaut antérieur ; oracle 3 — CSP")
        self.depot.enregistrement(couvre=("ATST1", "ATST2"), ecart=("ATST2",),
                                  etapes=[etape(notes=""), ecart])
        code, sortie = self.lancer()
        self.assertEqual(code, 0, sortie)
        self.assertIn("ATST : 2 cochée(s) à preuve, 2 couverte(s), 0 en dette", sortie)
        # Mutant : la même étape sans `base_verdict: FAIL` (ce qu'écrit une étape sans écart).
        self.depot.enregistrement(couvre=("ATST1", "ATST2"), ecart=("ATST2",),
                                  etapes=[etape(notes=""), dict(ecart, base_verdict=None)])
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("échoue aussi à la base", sortie)

    def test_enregistrement_spec_exemple_mutant_etape_vide_echoue(self):
        """Mutant : une etape sans oracles ni trace ⇒ la garde DOIT echouer."""
        self.ecrire_exemple_adep(vider_etape=2)
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("étape 3 vide ou incomplète", sortie)

    def test_dossier_brut_non_conforme_ignore(self):
        brut = self.depot.racine / cacc.DOSSIER / "2026-10-07-adoc171"
        brut.mkdir(parents=True)
        (brut / "capture.json").write_text("{}", encoding="utf-8")
        self.depot.plan(ligne(" ", "ATST1"))
        self.assertEqual(self.lancer()[0], 0)


if __name__ == "__main__":
    unittest.main()
