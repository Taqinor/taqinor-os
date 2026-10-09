"""ALEA43 — scripts/check_retard_unique.py (fixtures texte).

    python -m unittest scripts.tests.test_check_retard_unique -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_retard_unique as guard  # noqa: E402

AILLEURS = "backend/django_core/apps/crm/selectors.py"

LECTURE = '''
from .models import RelanceEtape

def en_retard(company, today):
    return RelanceEtape.objects.filter(company=company, due_date__lt=today)
'''

LECTURE_COMPARE = '''
from .models import RelanceEtape

def retardataires(etapes, today):
    return [e for e in etapes if e.due_date < today]
'''

LECTURE_VIA_SEUIL = '''
from .models import RelanceEtape

def en_retard(company, today):
    seuil = seuil_retard(company, today)
    return RelanceEtape.objects.filter(due_date__lt=seuil)
'''


class GardeTests(unittest.TestCase):
    def test_signale_comparaison_hors_source(self):
        violations, _ = guard.evaluer({AILLEURS: LECTURE}, {})
        self.assertEqual(len(violations), 1)
        self.assertIn("en_retard", violations[0])
        self.assertIn("due_date__lt=", violations[0])
        violations, _ = guard.evaluer({AILLEURS: LECTURE_COMPARE}, {})
        self.assertEqual(len(violations), 1)

    def test_accepte_source_unique(self):
        """Test-du-test : retirer controle_suivi.py de la source autorisée
        ferait échouer ce test."""
        violations, _ = guard.evaluer({guard.SOURCE_UNIQUE: LECTURE}, {})
        self.assertEqual(violations, [])
        violations, _ = guard.evaluer({guard.SOURCE_UNIQUE: LECTURE}, {},
                                      source_unique="autre.py")
        self.assertEqual(len(violations), 1)

    def test_exception_nommee(self):
        cle = f"{AILLEURS}::en_retard"
        violations, mortes = guard.evaluer({AILLEURS: LECTURE},
                                           {cle: "raison"})
        self.assertEqual((violations, mortes), ([], []))
        _, mortes = guard.evaluer({AILLEURS: "x = 1\n"}, {cle: "raison"})
        self.assertEqual(mortes, [cle])

    def test_lecture_via_seuil_retard_acceptee(self):
        violations, _ = guard.evaluer({AILLEURS: LECTURE_VIA_SEUIL}, {})
        self.assertEqual(violations, [])

    def test_fichier_sans_relance_etape_hors_perimetre(self):
        src = LECTURE.replace("RelanceEtape", "Activity")
        violations, _ = guard.evaluer({AILLEURS: src}, {})
        self.assertEqual(violations, [])

    def test_aucune_cle_par_numero_de_ligne(self):
        for cle in guard.EXCEPTIONS:
            fichier, _, symbole = cle.partition("::")
            self.assertTrue(symbole and not symbole.isdigit(), cle)
            self.assertNotRegex(cle, r":\d+$")

    def test_depot_vert(self):
        self.assertEqual(guard.main([]), 0)


if __name__ == "__main__":
    unittest.main()
