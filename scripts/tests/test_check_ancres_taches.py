"""Tests de scripts/check_ancres_taches.py (AMET83). Stdlib pur, depot jetable.

    python -m unittest scripts.tests.test_check_ancres_taches -v
"""
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

    def test_citation_entre_backticks_de_la_regle_nest_pas_une_ancre(self):
        self.assertEqual(self.depot.echecs("AAA9 — une ancre `(l.123)` ou `chemin:123` est citee"), [])

    def test_v2_rapporte_sans_echouer(self):
        self.assertEqual(self.depot.echecs("AAA6 — `mod.py::nope` `mod.py:9`", v2=("AAA6",)), [])

    def test_ni_glob_ni_dossier_ne_sont_des_ancres(self):
        self.assertEqual(self.depot.echecs("AAA7 — `chemin::Symbole` et `apps/*::X` et `apps/ventes/`"), [])


if __name__ == "__main__":
    unittest.main()
