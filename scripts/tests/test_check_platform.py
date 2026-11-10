"""ADCG77 — les trois bases gelées de ``check_platform.py`` (modèles hand-rollés,
ViewSets non scopés, marque) ne font que RÉTRÉCIR : une entrée sans offender
réel est nommée en rouge (``_cliquet.comparer``, message « entrée MORTE »).

Nouveau fichier car : aucun module ``scripts/tests`` pour ``check_platform.py``.
"""
import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent


def _charger():
    spec = importlib.util.spec_from_file_location(
        "check_platform_sous_test", ROOT / "scripts" / "check_platform.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BasesGeleesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _charger()

    def test_entree_morte_rouge(self):
        cas = [
            ("BASELINE_HANDROLLED_MODELS", self.m.check_handrolled_models,
             "handrolled_models.txt", "crm.ModeleDisparu"),
            ("BASELINE_UNSCOPED_VIEWSETS", self.m.check_unscoped_viewsets,
             "unscoped_viewsets.txt", "crm.ViewSetDisparu"),
            ("BASELINE_BRANDING", self.m.check_branding,
             "branding_hits.txt", "apps/crm/fichier_disparu.py"),
        ]
        for nom, garde, fichier, morte in cas:
            base = getattr(self.m, nom) | {morte}
            with mock.patch.object(self.m, nom, base):
                erreurs = garde()
            self.assertTrue(
                any(f"entrée MORTE de {fichier} : {morte}" in e for e in erreurs),
                f"{fichier} : entrée morte non signalée ({erreurs[:3]})")

    def test_arbre_reel_sans_entree_morte(self):
        for garde in (self.m.check_handrolled_models, self.m.check_unscoped_viewsets,
                      self.m.check_branding):
            erreurs = garde()
            self.assertEqual(erreurs, [], f"{garde.__name__} : {erreurs[:5]}")


if __name__ == "__main__":
    unittest.main()
