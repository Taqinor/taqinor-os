"""Tests de scripts/audit_registre.py (AMET91) — depot jetable, stdlib pure.

    python -m unittest scripts.tests.test_audit_registre -v

Pas de Django, pas de base, pas de reseau : un faux depot (unites.yml, plans,
dossiers, done_task.md) et, pour `claim`, un depot git nu LOCAL (jamais origin).
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import audit_registre as ar  # noqa: E402
import check_taches_cablage as ctc  # noqa: E402

UNITES = """version: 1
unites:

  - id: T1
    rang: 1
    declencheur: truc
    statut: audité
    groupe: ZZTST
    plan: docs/plans/PLAN_AUDIT_TRUC.md
    plans_alimentes: [docs/plans/PLAN_AUDIT_TRUC.md]
    dossier: docs/audits/2026-01-01-truc.md
"""


def taches(coches, ouvertes, prefixe="ZZTST", debut=1):
    lignes = []
    n = debut
    for _ in range(coches):
        lignes.append(f"- [x] {prefixe}{n} — fait. Files: `a.py`\n")
        n += 1
    for _ in range(ouvertes):
        lignes.append(f"- [ ] {prefixe}{n} — a faire. Files: `a.py`\n")
        n += 1
    return "".join(lignes)


class FauxDepot:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        (self.racine / "docs" / "plans").mkdir(parents=True)
        (self.racine / "docs" / "audits").mkdir(parents=True)
        self._sauve = (ar.ROOT, ctc.ROOT)
        ar.ROOT = ctc.ROOT = self.racine
        self.ecrire("docs/audits/unites.yml", UNITES)

    def ecrire(self, rel, contenu):
        chemin = self.racine / rel
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(contenu, encoding="utf-8")

    def plan(self, contenu):
        self.ecrire("docs/plans/PLAN_AUDIT_TRUC.md", contenu)

    def dossier(self):
        self.ecrire("docs/audits/2026-01-01-truc.md", "# dossier\n")

    def verifie(self, contenu):
        self.ecrire("docs/audits/2026-02-01-truc-verifie.md", contenu)

    def close(self):
        ar.ROOT, ctc.ROOT = self._sauve
        self.tmp.cleanup()


def sortie(fonction, *args):
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        code = fonction(*args)
    return code, tampon.getvalue()


class RegistreTests(unittest.TestCase):
    def setUp(self):
        self.depot = FauxDepot()
        self.addCleanup(self.depot.close)
        self.depot.dossier()
        # pas de sous-processus ici (lent sous Windows) : `claim` a ses tests.
        ancien = ar.claims_vivants
        ar.claims_vivants = lambda remote="origin": {}
        self.addCleanup(setattr, ar, "claims_vivants", ancien)

    def statut(self):
        lignes = ar.calculer()
        self.assertEqual(len(lignes), 1)
        return lignes[0]

    def test_statut_construit_a_95_pour_cent_et_verifie_du(self):
        self.depot.plan(taches(19, 1))                 # 95 %
        ligne = self.statut()
        self.assertEqual(ligne["statut"], "construit")
        code, texte = sortie(ar.cmd_du)
        self.assertIn("ZZTST", texte)
        self.assertIn("95", texte)

    def test_en_dessous_de_95_reste_audite(self):
        self.depot.plan(taches(18, 2))                 # 90 %
        self.assertEqual(self.statut()["statut"], "audité")

    def test_mutant_seuil_95_devient_50_est_detecte(self):
        self.depot.plan(taches(18, 2))
        ancien = ar.SEUIL_CONSTRUIT
        ar.SEUIL_CONSTRUIT = 50
        try:
            self.assertNotEqual(self.statut()["statut"], "audité")
        finally:
            ar.SEUIL_CONSTRUIT = ancien

    def test_bloquees_et_gated_ne_comptent_pas(self):
        self.depot.plan(taches(19, 0)
                        + "- [BLOCKED: hors perimetre] ZZTST90 — x\n"
                        + "- [ ] ZZTST91 — x (GATED fondateur) Files: `a.py`\n")
        self.assertEqual(self.statut()["statut"], "construit")

    def test_ledger_done_task_compte_les_archivees(self):
        self.depot.plan(taches(0, 1))
        self.depot.ecrire(
            "docs/done_task.md",
            "<!-- plan-progress-ledger v1\nZZTST=19\n-->\n")
        self.assertEqual(self.statut()["statut"], "construit")

    def test_du_50_jamais_verifie_puis_95_pas_verifie_depuis(self):
        self.depot.plan(taches(10, 10))                # 50 %
        _, texte = sortie(ar.cmd_du)
        self.assertIn("ZZTST", texte)
        self.depot.plan(taches(5, 15))                 # 25 %
        _, texte = sortie(ar.cmd_du)
        self.assertNotIn("ZZTST", texte)
        self.depot.plan(taches(20, 0))                 # 100 %
        self.depot.verifie("<!-- verifie | groupe: ZZTST | pct: 60 | "
                           "ecarts_s1_s2: 0 -->\n")
        _, texte = sortie(ar.cmd_du)
        self.assertIn("ZZTST", texte)                  # vérifié à 60 : clôture due
        self.depot.verifie("<!-- verifie | groupe: ZZTST | pct: 100 | "
                           "ecarts_s1_s2: 0 -->\n")
        _, texte = sortie(ar.cmd_du)
        self.assertNotIn("ZZTST", texte)

    def test_verifie_sans_ecart_donne_verifie_avec_ecart_non(self):
        self.depot.plan(taches(20, 0))
        self.depot.verifie("<!-- verifie | groupe: ZZTST | pct: 100 | "
                           "ecarts_s1_s2: 0 -->\n")
        self.assertEqual(self.statut()["statut"], "vérifié")
        self.depot.verifie("<!-- verifie | groupe: ZZTST | pct: 100 | "
                           "ecarts_s1_s2: 2 -->\n")
        self.assertEqual(self.statut()["statut"], "construit")

    def test_verifie_sans_marqueur_les_s1_s2_comptent(self):
        self.depot.plan(taches(20, 0))
        self.depot.verifie("# Vérifie\n**ASTK39 — S1** écart\n")
        self.assertEqual(self.statut()["statut"], "construit")

    def test_sans_dossier_a_auditer(self):
        (self.depot.racine / "docs/audits/2026-01-01-truc.md").unlink()
        self.depot.plan(taches(1, 1))
        self.assertEqual(self.statut()["statut"], "à auditer")

    def test_acceptation_nd_sans_garde(self):
        self.depot.plan(taches(20, 0))
        self.assertEqual(self.statut()["acceptation"], "n/d")

    def test_status_table_et_unites_jamais_reecrit(self):
        self.depot.plan(taches(20, 0))
        avant = (self.depot.racine / "docs/audits/unites.yml").read_bytes()
        code, texte = sortie(ar.cmd_status)
        self.assertEqual(code, 0)
        self.assertIn("T1", texte)
        self.assertIn("20/20", texte)
        self.assertEqual(
            avant, (self.depot.racine / "docs/audits/unites.yml").read_bytes())

    def test_prochain_id_max_plus_un_tous_plans_et_archive(self):
        self.depot.plan(taches(2, 1))                  # ZZTST1..3
        self.depot.ecrire("docs/PLAN2.md", taches(0, 1, debut=7))
        self.depot.ecrire("docs/done_task.md", "ZZTST1–ZZTST40 archive, ZZTSTX9\n")
        code, texte = sortie(ar.cmd_prochain_id, "ZZTST")
        self.assertEqual(texte.strip(), "ZZTST41")
        code, texte = sortie(ar.cmd_prochain_id, "QQQ")
        self.assertEqual(texte.strip(), "QQQ1")

    def test_check_dossier_manquant_echoue(self):
        self.depot.plan(taches(1, 0))
        self.assertEqual(sortie(ar.cmd_check)[0], 0)
        (self.depot.racine / "docs/audits/2026-01-01-truc.md").unlink()
        code, texte = sortie(ar.cmd_check)
        self.assertEqual(code, 1)
        self.assertIn("2026-01-01-truc.md", texte)

    def test_check_groupe_sans_plan_echoue(self):
        self.depot.plan(taches(1, 0, prefixe="AUTRE"))
        code, texte = sortie(ar.cmd_check)
        self.assertEqual(code, 1)
        self.assertIn("ZZTST", texte)


def git(cwd, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True,
                          capture_output=True, text=True)


class ClaimTests(unittest.TestCase):
    """`claim` contre un depot git nu LOCAL — jamais le vrai origin."""

    def setUp(self):
        self.depot = FauxDepot()
        self.addCleanup(self.depot.close)
        self.nu = tempfile.TemporaryDirectory()
        self.addCleanup(self.nu.cleanup)
        git(self.nu.name, "init", "--bare", "-b", "main")
        racine = self.depot.racine
        git(racine, "init", "-b", "main")
        git(racine, "add", "-A")
        git(racine, "commit", "-m", "base")
        git(racine, "remote", "add", "origin", self.nu.name)
        git(racine, "push", "origin", "main")

    def test_claim_cree_la_branche_puis_refuse_la_seconde_fois(self):
        code, texte = sortie(ar.cmd_claim, "T1")
        self.assertEqual(code, 0, texte)
        heads = git(self.nu.name, "branch", "--list", "audit-T1").stdout
        self.assertIn("audit-T1", heads)
        code, texte = sortie(ar.cmd_claim, "T1")
        self.assertEqual(code, 1)
        self.assertIn("prise", texte)

    def test_claim_unite_inconnue(self):
        code, _ = sortie(ar.cmd_claim, "ZZ9")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
