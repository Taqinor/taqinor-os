"""AMOT75 - symboles publics du moteur (constants*.py, bareme.py) sans lecteur de production."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_services_appeles as csa  # noqa: E402

MOTEUR = "backend/django_core/apps/ventes/quote_engine"


def _arbre(tmp, constants, lecteurs=None):
    r = Path(tmp)
    (r / MOTEUR).mkdir(parents=True)
    (r / MOTEUR / "constants.py").write_text(constants, encoding="utf-8")
    for nom, src in (lecteurs or {}).items():
        p = r / "backend/django_core/apps/ventes" / nom
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src, encoding="utf-8")
    return r


class SymbolesMoteurTests(unittest.TestCase):
    def test_constante_sans_lecteur_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, "KWH_PRICE = 1.2\nTARIF = 3\n", {"views.py": "from x import TARIF\nprint(TARIF)\n"})
            self.assertEqual(csa.symboles_moteur_sans_lecteur(r), [f"{MOTEUR}/constants.py::KWH_PRICE"])
            erreurs = csa.verifier_symboles_moteur(r, set())
            self.assertEqual(len(erreurs), 1)
            self.assertIn("KWH_PRICE", erreurs[0])

    def test_retirer_un_lecteur_nomme_le_symbole(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, "TARIF = 3\n", {"views.py": "print(TARIF)\n"})
            self.assertEqual(csa.symboles_moteur_sans_lecteur(r), [])
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, "TARIF = 3\n", {"views.py": "print(1)\n"})
            self.assertEqual(len(csa.symboles_moteur_sans_lecteur(r)), 1)

    def test_acces_dynamique_par_attribut_resolu(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, "def tarif_mt_moyen(): return 1\n",
                       {"x.py": "import c8221\nprint(c8221.tarif_mt_moyen())\n"})
            self.assertEqual(csa.symboles_moteur_sans_lecteur(r), [])

    def test_lecteur_test_ne_compte_pas(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, "TARIF = 3\n")
            t = r / "backend/django_core/apps/ventes/tests/test_x.py"
            t.parent.mkdir(parents=True)
            t.write_text("print(TARIF)\n", encoding="utf-8")
            self.assertEqual(len(csa.symboles_moteur_sans_lecteur(r)), 1)

    def test_lecture_interne_compte(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, "BASE = 3\n\n\ndef calc():\n    return BASE\n", {"v.py": "calc()\n"})
            self.assertEqual(csa.symboles_moteur_sans_lecteur(r), [])

    def test_exception_motivee_et_cle_morte(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, "TSS = 1\n")
            cle = f"{MOTEUR}/constants.py::TSS"
            self.assertEqual(csa.verifier_symboles_moteur(r, {cle}), [])
            erreurs = csa.verifier_symboles_moteur(r, {cle, f"{MOTEUR}/constants.py::MORT"})
            self.assertEqual(len(erreurs), 1)
            self.assertIn("cle morte", erreurs[0])

    def test_depot_reel_vert(self):
        self.assertEqual(csa.verifier_symboles_moteur(), [])


if __name__ == "__main__":
    unittest.main()
