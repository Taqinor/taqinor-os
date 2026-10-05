"""Tests de scripts/check_duplicats_litteraux.py (ACAL345, C-ACAL-146).

Stdlib pur (unittest), arbre factice jetable — aucune base, aucun node.
    python -m unittest scripts.tests.test_check_duplicats_litteraux -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_duplicats_litteraux as cdl  # noqa: E402


def corps(n, prefixe="valeur"):
    """n lignes significatives distinctes (aucune n'est de la ponctuation)."""
    return "".join(f"const {prefixe}{i} = calcule({i}, 'x{i}');\n"
                   for i in range(n))


class FauxArbre(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.racine = Path(self.tmp.name)
        sauvegarde = (cdl.ROOT, cdl.BASELINE_PATH)
        cdl.ROOT = self.racine
        cdl.BASELINE_PATH = self.racine / "allow.txt"

        def restaure():
            cdl.ROOT, cdl.BASELINE_PATH = sauvegarde
        self.addCleanup(restaure)

    def ecrit(self, rel, contenu):
        chemin = self.racine / rel
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(contenu, encoding="utf-8")

    def duplicats(self):
        trouves, _ = cdl.analyse(self.racine)
        return trouves

    def test_six_lignes_identiques_dans_deux_fichiers_sont_detectees(self):
        self.ecrit("frontend/src/pages/a/A.jsx", "// a\n" + corps(6) + "}\n")
        self.ecrit("frontend/src/features/b/B.jsx", corps(6))
        trouves = self.duplicats()
        self.assertEqual(len(trouves), 1)
        self.assertEqual(trouves[0].fichiers,
                         ["frontend/src/features/b/B.jsx",
                          "frontend/src/pages/a/A.jsx"])
        self.assertEqual(trouves[0].nb_lignes, 6)

    def test_cinq_lignes_ne_le_sont_pas(self):
        self.ecrit("frontend/src/pages/a/A.jsx", corps(5))
        self.ecrit("frontend/src/features/b/B.jsx", corps(5))
        self.assertEqual(self.duplicats(), [])

    def test_difference_d_espaces_ne_masque_pas_la_copie(self):
        self.ecrit("frontend/src/pages/a/A.jsx", corps(6))
        espace = "".join("    " + ligne.replace(" = ", "   =   ") + "\n\n"
                         for ligne in corps(6).splitlines())
        self.ecrit("apps/web/src/lib/b.ts", espace)
        self.assertEqual(len(self.duplicats()), 1)

    def test_ponctuation_commentaires_et_imports_ne_comptent_pas(self):
        # 5 lignes significatives seulement, noyees dans du bruit commun.
        bruit = "import x from 'y'\n// commentaire\n});\n}\n)\n"
        self.ecrit("frontend/src/pages/a/A.jsx", bruit + corps(5) + bruit)
        self.ecrit("frontend/src/features/b/B.jsx", bruit + corps(5) + bruit)
        self.assertEqual(self.duplicats(), [])

    def test_meme_fichier_n_est_pas_un_duplicata(self):
        self.ecrit("frontend/src/pages/a/A.jsx", corps(6) + corps(6))
        self.assertEqual(self.duplicats(), [])

    def test_hors_des_quatre_racines_rien_n_est_lu(self):
        self.ecrit("frontend/src/components/A.jsx", corps(6))
        self.ecrit("frontend/src/pages/a/A.jsx", corps(6))
        self.assertEqual(self.duplicats(), [])

    def test_fenetres_chevauchantes_fusionnees_en_un_bloc(self):
        self.ecrit("frontend/src/pages/a/A.jsx", corps(10))
        self.ecrit("backend/django_core/apps/ventes/quote_engine/b.py",
                   corps(10))
        trouves = self.duplicats()
        self.assertEqual(len(trouves), 1)
        self.assertEqual(trouves[0].nb_lignes, 10)

    def test_bloc_deja_en_base_est_tolere(self):
        self.ecrit("frontend/src/pages/a/A.jsx", corps(6))
        self.ecrit("frontend/src/features/b/B.jsx", corps(6))
        self.assertEqual(cdl.main([]), 1)              # pas de base : rouge
        cdl.ecrire_base({d.cle for d in self.duplicats()})
        self.assertEqual(cdl.main([]), 0)              # en base : vert
        self.ecrit("apps/web/src/c.ts", corps(7, "autre"))
        self.ecrit("frontend/src/pages/c/C.jsx", corps(7, "autre"))
        self.assertEqual(cdl.main([]), 1)              # nouveau bloc : rouge

    def test_la_base_ne_peut_que_retrecir(self):
        self.ecrit("frontend/src/pages/a/A.jsx", corps(6))
        self.ecrit("frontend/src/features/b/B.jsx", corps(6))
        cdl.ecrire_base(set())
        self.assertEqual(cdl.main(["--write-baseline"]), 1)
        self.assertEqual(cdl.charger_base(), set())
        self.assertEqual(
            cdl.main(["--write-baseline", "--autoriser-croissance"]), 0)
        self.assertEqual(len(cdl.charger_base()), 1)

    def test_perimetre_calepinage(self):
        motif = cdl.PERIMETRES["calepinage"]
        self.assertTrue(motif.search("frontend/src/features/calepinage/x.js"))
        self.assertTrue(motif.search("frontend/src/pages/ventes/ToitureDesign.jsx"))
        self.assertFalse(motif.search("frontend/src/pages/crm/ClientList.jsx"))


if __name__ == "__main__":
    unittest.main()
