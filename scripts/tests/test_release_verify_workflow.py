"""ADCG68 — ordre des étapes du nocturne `release-verify.yml`.

`web-full` doit construire le site (`npm run build`) AVANT vitest (`npm test`),
comme `ci.yml::web-build-test` : sinon `ensureBuilt` lance la construction
pendant vitest et les tests qui lisent `dist/client` échouent (C-ADCG-036).
    python -m unittest scripts.tests.test_release_verify_workflow -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _runs(workflow: str, job: str) -> list[str]:
    doc = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))
    return [str(s.get("run", "")).strip() for s in doc["jobs"][job]["steps"]]


class OrdreWebFullTests(unittest.TestCase):
    def _index(self, runs: list[str], commande: str) -> int:
        trouves = [i for i, r in enumerate(runs) if r == commande]
        self.assertEqual(len(trouves), 1, f"« {commande} » attendu une fois : {runs}")
        return trouves[0]

    def test_build_avant_vitest(self):
        runs = _runs("release-verify.yml", "web-full")
        self.assertLess(self._index(runs, "npm run build"), self._index(runs, "npm test"))

    def test_patron_ci_construit_avant_de_tester(self):
        # web-build-test enchaîne apps/web puis apps/yanbow-web : chaque site construit avant de tester.
        runs = _runs("ci.yml", "web-build-test")
        builds = [i for i, r in enumerate(runs) if r == "npm run build"]
        tests = [i for i, r in enumerate(runs) if r == "npm test"]
        self.assertTrue(builds and len(builds) == len(tests), runs)
        for build, test in zip(builds, tests):
            self.assertLess(build, test)


class AlerteNocturneTests(unittest.TestCase):
    def test_le_corps_nomme_les_jobs_non_verts(self):
        # ATST42 — l'issue nightly-alert liste les jobs non verts de la nuit.
        doc = yaml.safe_load((WORKFLOWS / "release-verify.yml").read_text(encoding="utf-8"))
        etapes = {e.get("name"): e for e in doc["jobs"]["alert-on-repeated-failure"]["steps"]}
        decision = etapes["Decider s'il faut alerter (scripts/nightly_alert_gate.py)"]["run"]
        self.assertIn('--job "backend-full=', decision)
        self.assertIn("--jobs-non-verts", decision)
        self.assertIn('rouges=$ROUGES', decision)
        alerte = etapes["Ouvrir/mettre à jour l'issue d'alerte (2 nuits rouges de suite)"]
        self.assertEqual(alerte["env"]["ROUGES"], "${{ steps.decision.outputs.rouges }}")
        self.assertIn("`Jobs non verts : ${rouges}`", alerte["with"]["script"])
        self.assertIn("pdf/slow non prouvés cette nuit", alerte["with"]["script"])


if __name__ == "__main__":
    unittest.main()
