"""ENF12 — tests de scripts/check_cve_severite.py (sans réseau)."""
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

cve = importlib.import_module("check_cve_severite")

RAPPORT = {"dependencies": [
    {"name": "django", "version": "5.1.15", "vulns": [
        {"id": "PYSEC-1", "aliases": ["GHSA-aaaa", "CVE-1"], "fix_versions": ["5.2.17"]},
        {"id": "PYSEC-1", "aliases": ["GHSA-aaaa"], "fix_versions": ["5.2.17"]},
    ]},
    {"name": "lib", "version": "1.0", "vulns": [
        {"id": "PYSEC-2", "aliases": ["GHSA-bbbb"], "fix_versions": ["1.1"]},
    ]},
    {"name": "sain", "version": "2.0", "vulns": []},
]}


def faux_osv(sev_par_id):
    def lire(url):
        ghsa = url.rsplit("/", 1)[1]
        if ghsa not in sev_par_id:
            raise OSError("injoignable")
        return {"database_specific": {"severity": sev_par_id[ghsa]}}
    return lire


class CveSeveriteTests(unittest.TestCase):
    def test_dedoublonne(self):
        self.assertEqual(len(cve.vulnerabilites(RAPPORT)), 2)

    def test_high_bloque(self):
        bloq, infos = cve.evaluer(RAPPORT, faux_osv({"GHSA-aaaa": "HIGH", "GHSA-bbbb": "MODERATE"}))
        self.assertEqual(len(bloq), 1)
        self.assertIn("django", bloq[0])
        self.assertEqual(len(infos), 1)

    def test_moderate_seul_passe(self):
        bloq, _ = cve.evaluer(RAPPORT, faux_osv({"GHSA-aaaa": "LOW", "GHSA-bbbb": "MODERATE"}))
        self.assertEqual(bloq, [])

    def test_severite_inconnue_bloque(self):
        bloq, _ = cve.evaluer(RAPPORT, faux_osv({"GHSA-aaaa": "LOW"}))
        self.assertEqual(len(bloq), 1)
        self.assertIn("INCONNUE", bloq[0])

    def test_sans_ghsa_bloque(self):
        rapport = {"dependencies": [{"name": "x", "version": "1", "vulns": [
            {"id": "PYSEC-9", "aliases": ["CVE-9"], "fix_versions": []}]}]}
        bloq, _ = cve.evaluer(rapport, faux_osv({}))
        self.assertEqual(len(bloq), 1)

    def test_rapport_vide_passe(self):
        self.assertEqual(cve.evaluer({"dependencies": []}, faux_osv({})), ([], []))


if __name__ == "__main__":
    unittest.main()
