"""Tests de scripts/check_err_prod.py (BPQ13). Stdlib pur.

    python -m unittest scripts.tests.test_check_err_prod -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_err_prod as cep  # noqa: E402 — après sys.path/setup() (D-ENF22)

BONNE = ("- [ ] ERR-PROD-CRM-LISTE-500 — [crm] 500 sur la liste. Signature: exception|GET|/api/x|500|abc. "
         "Test rouge DANS le module existant apps/crm/tests/test_views.py.")


class TestCheckErrProd(unittest.TestCase):
    def test_ligne_conforme(self):
        self.assertEqual(cep.verifier(BONNE), [])

    def test_lignes_non_err_prod_ignorees(self):
        self.assertEqual(cep.verifier("- [ ] ERR-JPB-X — rien"), [])

    def test_signature_manquante(self):
        e = cep.verifier(BONNE.replace("Signature:", "Sig"))
        self.assertTrue(any("Signature" in x for x in e))

    def test_test_rouge_manquant(self):
        e = cep.verifier(BONNE.replace("Test rouge DANS le module existant", "pas de test"))
        self.assertTrue(any("test rouge" in x for x in e))

    def test_fichier_par_erreur_refuse(self):
        e = cep.verifier(BONNE + " Voir test_err_crm_liste.py")
        self.assertTrue(any("test_err_" in x for x in e))

    def test_id_minuscule_refuse(self):
        e = cep.verifier(BONNE.replace("ERR-PROD-CRM-LISTE-500", "ERR-PROD-crm_liste"))
        self.assertTrue(any("hors" in x for x in e))

    def test_plan_actuel_conforme(self):
        self.assertEqual(cep.verifier(cep.PLAN.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main()
