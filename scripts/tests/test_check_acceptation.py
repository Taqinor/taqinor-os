"""Tests de scripts/check_acceptation.py (garde d'acceptation, AMET88).

Stdlib pur (unittest), aucun Django, aucune base, aucun docker, aucun reseau.
Depot jetable dans un dossier temporaire ; ``git init`` seulement pour les
tests de la base git (dette qui grossit). Lancer :
    python -m unittest scripts.tests.test_check_acceptation -v
"""
import contextlib
import copy
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

import check_acceptation as cacc  # noqa: E402 — après sys.path/setup() (D-ENF22)
import parcours_tables as cp  # noqa: E402 — après sys.path/setup() (D-ENF22)
import rejouer_parcours as rp  # noqa: E402 — après sys.path/setup() (D-ENF22)
import sonde  # noqa: E402 — après sys.path/setup() (D-ENF22)

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


# --- AMET98 : tables de parcours (validation statique) et rejeu hors docker ---
# Stdlib pur, dépôt jetable, sans Django : le rejeu lui-même tourne dans le conteneur (sonde.py).

VUES = ("class FactureViewSet:\n    def payer(self):\n        return 1\n\n\n"
        "def emettre():\n    pass\n")
MODELES = "class Facture:\n    statut = 'x'\n"

ETAPE = {  # schéma §D.1 : contrôlé par core/parcours.problemes_de_la_table
    "id": "PA9.01", "nom": "Payer", "proprietaire": "fac",
    "declencheur": {"type": "clic", "source": "apps/fac/views.py::FactureViewSet.payer"},
    "fonction_entree": "apps/fac/views.py::FactureViewSet.payer",
    "checkpoint": {"modifiable": True, "champs": ["statut"], "persistance": "apps/fac/models.py::Facture.statut"},
    "regle_aval": [{"type": "refus_409", "detail": "déjà payée"}],
    "taches": ["AFAC1"],
}
ETAPE_B = {  # dialecte `libelle` / `regles_aval` (AMET13/15/18/24)
    "id": "payer", "libelle": "Payer",
    "declencheur": {"type": "http", "source": "apps/fac/views.py::FactureViewSet.payer"},
    "fonction_entree": "apps/fac/views.py::emettre",
    "checkpoint": {"persistance": "apps/fac/models.py::Facture"},
    "regles_aval": [{"regle": "refus si déjà payée", "source": "apps/fac/views.py::emettre"}],
    "taches": ["AFAC1"],
}
MANQUANTE = {
    "id": "PA9.02", "libelle": "Relance", "manquante": True,
    "declencheur": {"manquant": True}, "fonction_entree": {"manquant": True},
    "checkpoint": {"persistance": "apps/fac/models.py::Facture"},
    "regles_aval": [{"regle": "émetteur présent", "source": "apps/fac/views.py::emettre"}],
}


def _table(*etapes, portes=True):
    t = {"parcours": "PA9", "pilote": "fac", "chemins_relatifs_a": "backend/django_core",
         "etapes": [copy.deepcopy(e) for e in etapes]}
    if portes:
        t["portes"] = [{"id": "p1", "source": "apps/fac/views.py::emettre"}]
    return t


class _Depot:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        app = self.racine / "backend" / "django_core" / "apps" / "fac"
        (app / "parcours").mkdir(parents=True)
        (app / "views.py").write_text(VUES, encoding="utf-8")
        (app / "models.py").write_text(MODELES, encoding="utf-8")

    def ecrire(self, table):
        (self.racine / "backend/django_core/apps/fac/parcours/PA9.json").write_text(
            json.dumps(table, ensure_ascii=False), encoding="utf-8")


def _echecs(table):
    d = _Depot()
    try:
        return cp.verifier_table("PA9.json", table, d.racine)
    finally:
        d.tmp.cleanup()


class ParcoursTests(unittest.TestCase):
    """AMET98 — `parcours_tables.py`, exécuté par `check_acceptation.py --parcours` (stage-names)."""

    def test_etape_sans_regle_aval_echoue_et_symbole_resolu_passe(self):
        echecs, _ = _echecs(_table(ETAPE))
        self.assertEqual(echecs, [])
        sans = copy.deepcopy(ETAPE)
        sans["regle_aval"] = []
        echecs, _ = _echecs(_table(sans))
        self.assertTrue(any("règle aval" in e for e in echecs), echecs)

    def test_etape_sans_checkpoint_echoue(self):
        for cle in ("checkpoint", "declencheur", "fonction_entree"):
            with self.subTest(cle=cle):
                sans = copy.deepcopy(ETAPE)
                del sans[cle]
                echecs, _ = _echecs(_table(sans))
                self.assertTrue(any(cle in e for e in echecs), echecs)

    def test_symbole_introuvable_echoue(self):
        faux = copy.deepcopy(ETAPE)
        faux["fonction_entree"] = "apps/fac/views.py::FactureViewSet.rembourser"
        echecs, _ = _echecs(_table(faux))
        self.assertTrue(any("rembourser" in e for e in echecs), echecs)
        faux = copy.deepcopy(ETAPE)
        faux["regle_aval"] = [{"type": "inventee"}]
        echecs, _ = _echecs(_table(faux))
        self.assertTrue(any("inventee" in e for e in echecs), echecs)

    def test_entree_qui_n_est_pas_une_reference_echoue(self):
        for etape in (ETAPE, ETAPE_B):
            deux = copy.deepcopy(etape)
            deux["fonction_entree"] = etape["fonction_entree"] + " puis apps/fac/views.py::emettre"
            echecs, _ = _echecs(_table(deux))
            self.assertTrue(any("fonction_entree" in e and "fichier::symbole" in e for e in echecs), echecs)

    def test_etape_manquante_rapportee_jamais_resolue(self):
        echecs, manquantes = _echecs(_table(ETAPE_B, MANQUANTE))
        self.assertEqual((echecs, manquantes), ([], ["PA9.02"]))
        mal = copy.deepcopy(MANQUANTE)
        mal["fonction_entree"] = "apps/fac/views.py::emettre"
        echecs, _ = _echecs(_table(ETAPE_B, mal))
        self.assertTrue(any("manquante" in e for e in echecs), echecs)

    def test_dialecte_regles_aval_meme_exigences(self):
        for cle in ("checkpoint", "declencheur", "fonction_entree", "regles_aval"):
            with self.subTest(cle=cle):
                sans = copy.deepcopy(ETAPE_B)
                del sans[cle]
                echecs, _ = _echecs(_table(sans))
                self.assertTrue(echecs, cle)
        faux = copy.deepcopy(ETAPE_B)
        faux["regles_aval"][0]["source"] = "apps/fac/views.py::absente"
        echecs, _ = _echecs(_table(faux))
        self.assertTrue(any("absente" in e for e in echecs), echecs)

    def test_symbole_imbrique_resolu_par_l_index_amet80(self):
        imbrique = copy.deepcopy(ETAPE)
        imbrique["fonction_entree"] = "apps/fac/views.py::creer._create"
        d = _Depot()
        self.addCleanup(d.tmp.cleanup)
        (d.racine / "backend/django_core/apps/fac/views.py").write_text(
            VUES + "\n\ndef creer():\n    try:\n        def _create():\n            pass\n    finally:\n        pass\n",
            encoding="utf-8")
        self.assertEqual(cp.verifier_table("PA9.json", _table(imbrique), d.racine)[0], [])

    def test_portes_vides_echouent_sauf_dette_gelee_qui_ne_fait_que_retrecir(self):
        for etape in (ETAPE, ETAPE_B):
            echecs, _ = _echecs(_table(etape, portes=False))
            self.assertTrue(any("portes" in e for e in echecs), echecs)
        cp.SANS_PORTES_GELEES.add("PA9")
        try:
            self.assertEqual(_echecs(_table(ETAPE_B, portes=False))[0], [])
            echecs, _ = _echecs(_table(ETAPE_B))
            self.assertTrue(any("gelée" in e for e in echecs), echecs)
        finally:
            cp.SANS_PORTES_GELEES.discard("PA9")

    def test_main_sur_depot_jetable(self):
        d = _Depot()
        self.addCleanup(d.tmp.cleanup)
        d.ecrire(_table(ETAPE))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cp.verifier_tout(racine=d.racine), 0)
        self.assertIn("1 table(s)", out.getvalue())
        sans = copy.deepcopy(ETAPE)
        del sans["checkpoint"]
        d.ecrire(_table(sans))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cp.verifier_tout(racine=d.racine), 1)
        self.assertIn("ÉCHEC", out.getvalue())

    def test_tables_reelles_vertes_par_la_garde_d_acceptation(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = cacc.main(["--parcours"])
        self.assertEqual(code, 0, out.getvalue())
        self.assertGreaterEqual(len(cp.charger_tables(ROOT)), 7)


class RejeuTests(unittest.TestCase):
    """Le rejeu lui-même tourne dans le conteneur (sonde.py) : ici, tout ce qui l'entoure."""

    def _resultats(self, verdict_9_01="PASS"):
        oracles = {o: "NA" for o in cacc.ORACLES}
        oracles.update({"1": "PASS", "2": "PASS"})
        return [{"id": "payer", "joue": True, "appel": "POST /api/django/fac/1/payer/ -> 200",
                 "oracles": oracles, "parcours": {"auto": "NA", "checkpoint": "PASS", "aval": "PASS"},
                 "notes": "", "verdict": verdict_9_01}]

    def test_etapes_d_enregistrement_conformes_au_contrat_amet88(self):
        table = _table(ETAPE_B, MANQUANTE, dict(ETAPE_B, id="PA9.03", taches=[]))
        res = self._resultats() + [dict(self._resultats()[0], id="PA9.03")]
        etapes, ignorees = rp.etapes_enregistrement(table, res)
        self.assertEqual([e["id"] for e in etapes], ["payer"])
        self.assertTrue(all(cacc._etape_complete(e) for e in etapes))
        self.assertEqual(etapes[0]["taches"], ["AFAC1"])
        self.assertIn("PA9.02", " ".join(ignorees))   # manquante : rapportée, jamais jouée
        self.assertIn("PA9.03", " ".join(ignorees))   # sans tâche : jouée, rien à couvrir

    def test_oracle_de_parcours_en_echec_fait_tomber_l_etape(self):
        res = self._resultats()
        res[0]["parcours"]["aval"] = "FAIL"
        etapes, _ = rp.etapes_enregistrement(_table(ETAPE_B), res)
        self.assertEqual(etapes[0]["verdict"], "FAIL")

    def test_programme_dans_une_transaction_annulee(self):
        prog = rp.programme(_table(ETAPE_B), {"modele": "fac.Facture", "enregistrement": "1"}, 60)
        self.assertIn("set_rollback(True)", prog)
        self.assertIn(rp.MARQUE, prog)

    def test_source_envoyee_au_conteneur_autonome(self):
        """Les fonctions envoyées en ligne ne lisent aucun nom du module hors du programme lui-même."""
        import builtins
        ns = {}
        source = rp.EN_TETE_CONTENEUR + "\n\n".join(rp.inspect.getsource(f) for f in rp._CONTENEUR)
        exec(compile(source, "conteneur", "exec"), ns)
        self.assertIn("_jouer", ns)

        def noms(code):
            yield from code.co_names
            for c in code.co_consts:
                if hasattr(c, "co_names"):
                    yield from noms(c)
        for f in rp._CONTENEUR:
            with self.subTest(fonction=f.__name__):
                inconnus = {n for n in noms(ns[f.__name__].__code__) if n in vars(rp)} - set(ns) - set(vars(builtins))
                self.assertEqual(inconnus, set())

    def test_dry_run_n_execute_rien_et_table_invalide_refusee(self):
        appels = []

        def executer(*a):
            appels.append(a)
            return 0, "", ""
        d = _Depot()
        self.addCleanup(d.tmp.cleanup)
        d.ecrire(_table(ETAPE_B))
        argv = ["PA9", "--enregistrement", "1", "--modele", "fac.Facture", "--racine", str(d.racine)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rp.main(argv + ["--dry-run"], executer=executer), 0)
        self.assertEqual(appels, [])
        sans = copy.deepcopy(ETAPE_B)
        del sans["checkpoint"]
        d.ecrire(_table(sans))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(rp.main(argv, executer=executer), 1)
        self.assertEqual(appels, [])
        self.assertIn("ÉCHEC", out.getvalue())

    def test_rejeu_complet_ecrit_l_enregistrement_via_l_ecrivain_partage(self):
        d = _Depot()
        self.addCleanup(d.tmp.cleanup)
        d.ecrire(_table(ETAPE_B))
        sortie = (rp.MARQUE + json.dumps(self._resultats()) + "\n"
                  + sonde.MARQUE + json.dumps({"verdict": "REPRO", "base_inchangee": True, "observe": ""}) + "\n")
        ecrits = []
        argv = ["PA9", "--enregistrement", "1", "--modele", "fac.Facture", "--racine", str(d.racine)]
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = rp.main(argv, executer=lambda *a: (0, sortie, ""),
                           ecrire=lambda g, charge: ecrits.append((g, charge)) or 0)
        self.assertEqual(code, 0, out.getvalue())
        self.assertEqual(ecrits[0][0], "PA9")
        self.assertEqual(ecrits[0][1]["couvre"], ["AFAC1"])
        # base modifiée = jamais d'enregistrement
        sale = sortie.replace('"base_inchangee": true', '"base_inchangee": false')
        ecrits.clear()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(rp.main(argv, executer=lambda *a: (1, sale, ""),
                                     ecrire=lambda g, c: ecrits.append(g) or 0), 1)
        self.assertEqual(ecrits, [])


if __name__ == "__main__":
    unittest.main()
