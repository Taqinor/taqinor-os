"""ENF14 — forme du fichier unique des exceptions permanentes signées."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _exceptions_permanentes as ep  # noqa: E402

CATEGORIES_APPROUVEES = {
    "migration_safety", "safe_migrations", "tenant_exempt_models",
    "dockerignore_racine", "money_decimal_places", "tests_sautes_environnement",
}


class ExceptionsPermanentesTests(unittest.TestCase):
    def test_seules_les_categories_approuvees(self):
        self.assertEqual(set(ep.categories()), CATEGORIES_APPROUVEES)

    def test_chaque_categorie_a_une_raison(self):
        for nom, c in ep.categories().items():
            self.assertTrue(c["raison"], nom)

    def test_entrees_chargees(self):
        self.assertIn("compta.RegleInterSociete", ep.charger("tenant_exempt_models"))
        self.assertTrue(ep.charger("migration_safety"))
        self.assertEqual(ep.charger("inconnue"), set())

    def test_migrations_historiques_existent(self):
        for cat in ("migration_safety", "safe_migrations"):
            for rel in ep.charger(cat):
                self.assertTrue((ROOT / rel).is_file(), f"{cat}: {rel} absent")

    def test_anciens_fichiers_supprimes(self):
        for nom in ("migration_safety_allow.txt", "safe_migrations_allow.txt",
                    "tenant_exempt_models.txt", "dockerignore_racine_allow.txt"):
            self.assertFalse((ROOT / "scripts" / nom).exists(), nom)


if __name__ == "__main__":
    unittest.main()
