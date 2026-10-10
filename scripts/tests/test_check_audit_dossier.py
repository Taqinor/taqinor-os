"""Tests de scripts/check_audit_dossier.py (AMET92) — depot jetable, stdlib pure.

    python -m unittest scripts.tests.test_check_audit_dossier -v

Le faux depot embarque les VRAIS GABARIT_DOSSIER.md et METHODE.md (le lint les lit :
source unique des regles), plus un plan, decisions.yml et des sondes jetables.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_audit_dossier as cad  # noqa: E402
import check_taches_cablage as ctc  # noqa: E402

COUT = "Coût : H0 S1 O1 F0 · jetons sous-agents ≈ 1,2 M · tâches 1."
LIGNE = ("| C-ZZ-001 | P1.1 | C2 | S2 | `a/b.py::f` | observé → attendu | "
         "`docs/audits/sondes/ZZ/C-ZZ-001.py` | ZZ1 |")


def dossier(lignes=(LIGNE,), constats=None, decisions=("D-OK",), cout=COUT,
            marqueur="dossier-v3", ordre=None, extra="", taches=1):
    n = len(lignes) if constats is None else constats
    sections = ordre or [
        "## 1. Charte", "## 2. Couverture", "## 3. Constats",
        "## 4. Réfutés, requalifiés, fusionnés", "## 5. Non-risques",
        "## 6. Décisions", "## 7. Optionnel (jamais une tâche)",
        "## 8. Limites, non couvert, écarts", "## 9. Coût et routage"]
    corps = {
        "## 1. Charte": "| Champ | Valeur |\n|---|---|\n| Niveau | L2 |",
        "## 2. Couverture": "| Lane | Modèle/effort | Chemins lus | Chemins NON "
                            "lus (raison) |\n|---|---|---|---|\n| A1 | s | x | y |",
        "## 3. Constats": "| C-id | Étape | Critère | Grav. | fichier::symbole "
                          "| Observé → attendu | Sonde | Tâche(s) |\n"
                          "|---|---|---|---|---|---|---|---|\n"
                          + "\n".join(lignes),
        "## 4. Réfutés, requalifiés, fusionnés":
            "| Constat | Verdict | Argument |\n|---|---|---|",
        "## 5. Non-risques": "| Zone | Preuve | Valide tant que |\n|---|---|---|",
        "## 6. Décisions": "| D-id (`docs/audits/decisions.yml`) | Question | "
                           "Statut | Tâches |\n|---|---|---|---|\n"
                           + "\n".join(f"| {d} | q | ok | ZZ1 |" for d in decisions),
        "## 7. Optionnel (jamais une tâche)": "- rien",
        "## 8. Limites, non couvert, écarts": "- Non couvert : rien",
        "## 9. Coût et routage": cout,
    }
    texte = (f"# Audit ZZ « t » — 2026-01-01 — L2\n<!-- {marqueur} | groupe: ZZ | "
             f"base: abc1234 | fraicheur: abc1234 | constats: {n} | taches: "
             f"{taches} | decisions: {len(decisions)} -->\n\n")
    for s in sections:
        texte += s + "\n" + corps.get(s, "") + "\n\n"
    return texte + extra


class FauxDepot:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        for rel in ("docs/audits/GABARIT_DOSSIER.md", "docs/audits/METHODE.md"):
            (self.racine / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / rel, self.racine / rel)
        self._sauve = (cad.ROOT, ctc.ROOT)
        cad.ROOT = ctc.ROOT = self.racine
        self.ecrire("docs/audits/decisions.yml",
                    "version: 1\ndecisions:\n  - id: D-OK\n    reponse: a\n")
        self.ecrire("docs/audits/sondes/ZZ/C-ZZ-001.py", "SONDE = {}\n")
        self.plan("- [ ] ZZ1 — tache. C-ZZ-001 Files: `a.py`\n")

    def ecrire(self, rel, contenu):
        chemin = self.racine / rel
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(contenu, encoding="utf-8")

    def plan(self, contenu):
        self.ecrire("docs/plans/PLAN_AUDIT_ZZ.md", contenu)

    def close(self):
        cad.ROOT, ctc.ROOT = self._sauve
        self.tmp.cleanup()


class DossierTests(unittest.TestCase):
    def setUp(self):
        self.depot = FauxDepot()
        self.addCleanup(self.depot.close)

    def erreurs(self, texte):
        self.depot.ecrire("docs/audits/2026-01-01-zz.md", texte)
        return cad.analyser(self.depot.racine / "docs/audits/2026-01-01-zz.md")

    def assertErreur(self, texte, morceau):
        trouvees = self.erreurs(texte)
        self.assertTrue(any(morceau in e for e in trouvees),
                        f"{morceau!r} absent de {trouvees}")

    def test_dossier_conforme_passe(self):
        self.assertEqual(self.erreurs(dossier()), [])

    def test_c_id_cite_par_une_tache_absent_du_dossier_echoue(self):
        self.depot.plan("- [ ] ZZ1 — x. C-ZZ-001 Files: `a.py`\n"
                        "- [ ] ZZ2 — y. C-ZZ-009 Files: `a.py`\n")
        self.assertErreur(dossier(taches=2), "C-ZZ-009")

    def test_dossier_v2_sans_marqueur_est_ignore(self):
        self.depot.ecrire("docs/audits/2026-01-01-zz.md", "# vieux\nrien\n")
        self.assertEqual(cad.dossiers_v3(), [])

    def test_ordre_des_sections(self):
        ordre = ["## 2. Couverture", "## 1. Charte", "## 3. Constats",
                 "## 4. Réfutés, requalifiés, fusionnés", "## 5. Non-risques",
                 "## 6. Décisions", "## 7. Optionnel (jamais une tâche)",
                 "## 8. Limites, non couvert, écarts", "## 9. Coût et routage"]
        self.assertErreur(dossier(ordre=ordre), "section")

    def test_sonde_statique_interdite_en_s1_s2_sur_critere_a_sonde(self):
        ligne = LIGNE.replace("`docs/audits/sondes/ZZ/C-ZZ-001.py`", "STATIQUE")
        self.assertErreur(dossier((ligne,)), "STATIQUE")
        # critere C3 : sonde non obligatoire -> accepte
        self.assertEqual(self.erreurs(dossier(
            (ligne.replace("| C2 |", "| C3 |"),))), [])

    def test_mutant_colonne_sonde_ignoree_est_detecte(self):
        ligne = LIGNE.replace("`docs/audits/sondes/ZZ/C-ZZ-001.py`", "STATIQUE")
        ancien = cad.regle_sonde
        cad.regle_sonde = lambda *a, **k: []
        try:
            self.assertEqual(self.erreurs(dossier((ligne,))), [])
        finally:
            cad.regle_sonde = ancien
        self.assertNotEqual(self.erreurs(dossier((ligne,))), [])

    def test_sonde_inexistante(self):
        ligne = LIGNE.replace("C-ZZ-001.py", "C-ZZ-777.py")
        self.assertErreur(dossier((ligne,)), "C-ZZ-777.py")

    def test_s1_s2_sans_tache_ou_raison(self):
        ligne = LIGNE.replace("| ZZ1 |", "| |")
        self.assertErreur(dossier((ligne,)), "C-ZZ-001")
        ok = LIGNE.replace("| ZZ1 |", "| sans tâche : doublon de C-ZZ-002 |")
        self.depot.plan("- [ ] ZZ1 — x. Files: `a.py`\n")
        self.assertEqual(self.erreurs(dossier((ok,), taches=0)), [])

    def test_tache_citee_introuvable(self):
        self.assertErreur(dossier((LIGNE.replace("ZZ1", "ZZ99"),)), "ZZ99")

    def test_ancre_fichier_ligne_interdite(self):
        self.assertErreur(dossier((LIGNE.replace("a/b.py::f", "a/b.py:12"),)),
                          "ancre")

    def test_ligne_trop_longue(self):
        self.assertErreur(dossier(extra="x" * 450 + "\n"), "400")

    def test_interdits(self):
        for texte, morceau in (("lane VX12-3\n", "interdit"),
                               ("voir FABLE § 4\n", "interdit"),
                               ("a@b.fr\n", "interdit"),
                               ("- [ ] ZZ5 — tache\n", "interdit"),
                               ("```\n1\n2\n3\n4\n5\n6\n```\n", "bloc de code")):
            with self.subTest(texte=texte):
                self.assertErreur(dossier(extra=texte), morceau)

    def test_decision_absente_de_decisions_yml(self):
        self.assertErreur(dossier(decisions=("D-OK", "D-NOPE")), "D-NOPE")

    def test_si_a_dans_une_tache_du_groupe(self):
        self.depot.plan("- [ ] ZZ1 — Si (a) on fait. C-ZZ-001 Files: `a.py`\n")
        self.assertErreur(dossier(), "Si (a)")

    def test_ligne_de_cout(self):
        self.assertErreur(dossier(cout="Coût : beaucoup"), "coût")

    def test_compteurs_de_l_en_tete(self):
        self.assertErreur(dossier(constats=7), "constats")

    def test_methode_plafonds(self):
        racine = self.depot.racine
        (racine / ".claude/skills/audit").mkdir(parents=True)
        (racine / ".claude/skills/audit/SKILL.md").write_text("x\n" * 81)
        (racine / "docs/audits/METHODE.md").write_text("x\n" * 451)
        erreurs = cad.verifier_methode()
        self.assertEqual(len(erreurs), 2)
        (racine / ".claude/skills/audit/SKILL.md").write_text("x\n" * 80)
        (racine / "docs/audits/METHODE.md").write_text("x\n" * 450)
        self.assertEqual(cad.verifier_methode(), [])


if __name__ == "__main__":
    unittest.main()
