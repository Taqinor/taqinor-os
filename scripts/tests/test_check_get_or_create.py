"""ADEP29 - scripts/check_get_or_create.py : lecture seule, cles de contenu."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_get_or_create as guard  # noqa: E402

APPEL = "def creer(a):\n    return Foo.objects.get_or_create(nom=a)\n"


class Depot(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.app = self.tmp / "backend" / "django_core" / "apps" / "x"
        self.app.mkdir(parents=True)
        (self.tmp / "docs").mkdir()
        self.sauve = (guard.ROOT, guard.DJANGO_CORE, guard.APPS_DIR, guard.AUDIT_DOC)
        guard.ROOT = self.tmp
        guard.DJANGO_CORE = self.tmp / "backend" / "django_core"
        guard.APPS_DIR = guard.DJANGO_CORE / "apps"
        guard.AUDIT_DOC = self.tmp / "docs" / "get-or-create-audit.md"
        self.addCleanup(self.restaurer)

    def restaurer(self):
        guard.ROOT, guard.DJANGO_CORE, guard.APPS_DIR, guard.AUDIT_DOC = self.sauve

    def source(self, contenu):
        (self.app / "svc.py").write_text(contenu, encoding="utf-8")

    def lancer(self, *args):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = guard.main(list(args))
        return code


class GetOrCreateTests(Depot):
    def test_second_passage_reste_rouge(self):
        self.source(APPEL)
        self.assertEqual(self.lancer(), 1)
        self.assertEqual(self.lancer(), 1)  # le premier passage n'a rien ecrit
        self.assertFalse(guard.AUDIT_DOC.exists())

    def test_write_regenere(self):
        self.source(APPEL)
        self.assertEqual(self.lancer("--write"), 0)
        self.assertTrue(guard.AUDIT_DOC.exists())
        self.assertIn("svc.py::creer::Foo", guard.AUDIT_DOC.read_text(encoding="utf-8"))
        self.assertEqual(self.lancer(), 0)

    def test_insertion_amont_sans_faux_nouveau(self):
        self.source(APPEL)
        self.lancer("--write")
        self.source("import os\n\n\n# commentaire\n" + APPEL)  # decale l'appel
        self.assertEqual(self.lancer(), 0)

    def test_decalage_de_ligne_ne_rougit_plus(self):
        """AMET100 : la fonction descend de 20 lignes -> la garde reste verte SANS regeneration (cle par symbole)."""
        self.source(APPEL)
        self.assertEqual(self.lancer("--write"), 0)
        avant = guard.AUDIT_DOC.read_text(encoding="utf-8")
        self.source("# ligne de remplissage\n" * 20 + APPEL)
        self.assertEqual(self.lancer(), 0)
        self.assertEqual(guard.AUDIT_DOC.read_text(encoding="utf-8"), avant)  # le registre n'a pas bouge
        self.assertEqual(guard.TYPE_DE_CLE, "par_symbole")

    def test_depot_reel_vert(self):
        self.restaurer()
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(guard.main([]), 0, sortie.getvalue()[-500:])


if __name__ == "__main__":
    unittest.main()
