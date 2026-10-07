"""ALEA41 — le contrat `.importlinter` qui interdit au CRM d'importer les vues
d'autres domaines existe, et ses exceptions sont NOMMÉES (jamais un joker).

    python -m unittest scripts.tests.test_importlinter_crm_vues -v
"""
import configparser
import unittest
from pathlib import Path

CFG = Path(__file__).resolve().parents[2] / "backend" / "django_core" / ".importlinter"
SECTION = "importlinter:contract:crm-n-importe-pas-les-vues-d-autres-domaines"


def _cfg():
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(CFG, encoding="utf-8")
    return cp


def _lines(cp, key):
    return [x.strip() for x in cp[SECTION].get(key, "").splitlines() if x.strip()]


class ContratCrmVues(unittest.TestCase):
    def test_contrat_present_et_nomme(self):
        cp = _cfg()
        self.assertTrue(cp.has_section(SECTION))
        self.assertEqual(cp[SECTION]["type"], "forbidden")
        self.assertEqual(_lines(cp, "source_modules"), ["apps.crm"])
        self.assertEqual(set(_lines(cp, "forbidden_modules")),
                         {"apps.visites.views", "apps.ventes.views"})

    def test_exceptions_nommees_jamais_de_joker(self):
        for exc in _lines(_cfg(), "ignore_imports"):
            self.assertNotIn("*", exc)
            src, sep, dst = exc.partition(" -> ")
            self.assertTrue(sep and src.startswith("apps.crm") and dst, exc)


if __name__ == "__main__":
    unittest.main()
