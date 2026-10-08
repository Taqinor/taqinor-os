"""ADEP42 - un ImportError d'``app.*`` doit faire ECHOUER, pas sauter ; seule
l'absence d'une dependance TIERCE nommee autorise le skip."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._import_optionnel import verifier_import_optionnel  # noqa: E402


def _charger(code):
    """Reproduit le motif des fichiers de test : retourne (module, err)."""
    try:
        exec(code, {})
        return True, None
    except Exception as exc:
        verifier_import_optionnel(exc)  # re-leve si ce n'est pas une dep tierce
        return False, exc


class ImportStrictTests(unittest.TestCase):
    def test_nom_app_inexistant_fait_echouer(self):
        # Reproduit `from app.core.config import N_EXISTE_PAS` (ImportError).
        with self.assertRaises(ImportError):
            _charger("from tests._import_optionnel import N_EXISTE_PAS")

    def test_module_app_manquant_fait_echouer(self):
        with self.assertRaises(ModuleNotFoundError):
            _charger("import app.module_qui_nexiste_pas")

    def test_module_casse_fait_echouer(self):
        with self.assertRaises(SyntaxError):
            _charger("def (:")

    def test_dependance_tierce_absente_saute(self):
        ok, err = _charger("import dependance_tierce_inexistante_adep42")
        self.assertFalse(ok)
        self.assertIsInstance(err, ModuleNotFoundError)


if __name__ == "__main__":
    unittest.main()
