"""Tests de scripts/check_ancres_taches.py (AMET83). Stdlib pur, depot jetable.

    python -m unittest scripts.tests.test_check_ancres_taches -v
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

import check_ancres_taches as cat  # noqa: E402
import check_taches_cablage as ctc  # noqa: E402


class FauxDepot:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
        (self.racine / "docs" / "plans").mkdir(parents=True)
        (self.racine / "scripts").mkdir()
        (self.racine / "mod.py").write_text("class Foo:\n    def bar(self):\n        return 1\n\n\ndef haut():\n    pass\n",
                                            encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.racine, check=True)
        self._sauve = ctc.ROOT
        ctc.ROOT = self.racine

    def plan(self, *taches) -> list:
        (self.racine / "docs" / "plans" / "PLAN_AUDIT_X.md").write_text(
            "".join(f"- [ ] {t}\n" for t in taches), encoding="utf-8")
        return ["docs/plans/PLAN_AUDIT_X.md"]

    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       cwd=self.racine, check=True, capture_output=True)

    def valider(self, message="c"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def lancer(self, *args) -> tuple:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = cat.main(list(args))
        return code, sortie.getvalue()

    def fermer(self):
        ctc.ROOT = self._sauve
        self.tmp.cleanup()

    def echecs(self, *taches, v2=()) -> list:
        res = []
        for t in ctc.lire_taches(self.plan(*taches)):
            e, _ = cat.analyser_tache(t, t.identifiant in v2, self.racine)
            res += e
        return res


class AncresTests(unittest.TestCase):
    def setUp(self):
        self.depot = FauxDepot()
        self.addCleanup(self.depot.fermer)

    def test_symbole_absent_echoue_et_ligne_nue_echoue_en_v3(self):
        absent = self.depot.echecs("AAA1 — voir `mod.py::Foo.absent` fin")
        self.assertEqual([e[:2] for e in absent], [("AAA1", "mod.py::Foo.absent")])
        nue = self.depot.echecs("AAA2 — voir `mod.py:123` fin")
        self.assertEqual([e[1] for e in nue], ["`mod.py:123`"])
        self.assertEqual(len(self.depot.echecs("AAA3 — voir (l.12) fin")), 1)

    def test_symbole_present_passe_et_ligne_en_complement_passe(self):
        self.assertEqual(self.depot.echecs("AAA4 — `mod.py::Foo.bar` (l.2) et `mod.py:3`"), [])
        self.assertEqual(self.depot.echecs("AAA5 — `mod.py::haut`"), [])

    def test_methode_citee_sans_sa_classe_resout_si_elle_existe(self):
        # Revue du lot audit_deploy (ACRM68) : `module::test_x` vise une methode de classe de test.
        self.assertEqual(self.depot.echecs("AAA6 — `mod.py::bar` existe"), [])
        absent = self.depot.echecs("AAA7 — `mod.py::inexistante` n'existe pas")
        self.assertEqual([e[1] for e in absent], ["mod.py::inexistante"])

    def test_test_rouge_d_abord_nomme_un_test_a_creer(self):
        # La clause « Test rouge d'abord » nomme le test que la tache CREERA : jamais resolu
        # (regle (b) : il va dans le module de test EXISTANT, ou il n'existait pas encore).
        texte = ("AAA8 — Assertions existantes : `mod.py::haut` reste vert. Test rouge d'abord : "
                 "`mod.py::Foo.test_a_creer` (classe ajoutee), rouge avant. "
                 "Preuve en direct : n/a. Hors perimetre : `mod.py::autre_absente`.")
        self.assertEqual([e[1] for e in self.depot.echecs(texte)], ["mod.py::autre_absente"])

    def test_citation_entre_backticks_de_la_regle_nest_pas_une_ancre(self):
        self.assertEqual(self.depot.echecs("AAA9 — une ancre `(l.123)` ou `chemin:123` est citee"), [])

    def test_seule_une_tache_touchee_echoue(self):
        mauvaise = "BBB1 — voir `mod.py::absent` fin"
        self.depot.plan(mauvaise)
        self.depot.valider("base")
        code, sortie = self.depot.lancer("--base", "HEAD")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Rapport", sortie)
        self.depot.plan(mauvaise + " modifiee")
        self.assertEqual(self.depot.lancer("--base", "HEAD")[0], 1)
        self.depot.plan(mauvaise, "BBB2 — voir `mod.py::autre` fin")
        code, sortie = self.depot.lancer("--base", "HEAD")
        self.assertEqual(code, 1)
        self.assertIn("ECHEC BBB2", sortie)
        self.assertNotIn("ECHEC BBB1", sortie)

    def test_base_en_avance_sur_le_merge_base_ne_touche_pas_la_tache(self):
        # Revue du lot audit_deploy : une branche EN RETARD sur main ne touche pas une tâche que seul
        # main a modifiée — « touchée » se juge contre merge-base(base, HEAD), jamais la pointe de base.
        mauvaise = "BBB4 — voir `mod.py::absent` fin"
        self.depot.plan(mauvaise)
        self.depot.valider("merge-base")
        self.depot.git("branch", "pr")
        self.depot.plan(mauvaise + " precisee sur main", "BBB5 — neuve sur main seulement")
        self.depot.valider("main avance")
        self.depot.git("branch", "base-en-avance")
        self.depot.git("checkout", "-q", "pr")
        code, sortie = self.depot.lancer("--base", "base-en-avance")
        self.assertEqual(code, 0, sortie)
        self.assertIn("BBB4 : mod.py::absent", sortie)  # au rapport, pas bloquante
        self.depot.plan(mauvaise + " modifiee par la PR")
        code, sortie = self.depot.lancer("--base", "base-en-avance")
        self.assertEqual(code, 1, sortie)
        self.assertIn("ECHEC BBB4", sortie)

    def test_base_indisponible_traite_tout_comme_touche(self):
        self.depot.plan("BBB3 — voir `mod.py::absent` fin")
        os.environ.pop("GITHUB_ACTIONS", None)
        code, sortie = self.depot.lancer("--base", "refs/inexistante")
        self.assertEqual(code, 1)
        self.assertIn("base indisponible", sortie)

    def test_v2_rapporte_sans_echouer(self):
        self.assertEqual(self.depot.echecs("AAA6 — `mod.py::nope` `mod.py:9`", v2=("AAA6",)), [])

    def test_ni_glob_ni_dossier_ne_sont_des_ancres(self):
        self.assertEqual(self.depot.echecs("AAA7 — `chemin::Symbole` et `apps/*::X` et `apps/ventes/`"), [])


if __name__ == "__main__":
    unittest.main()
