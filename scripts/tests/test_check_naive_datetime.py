"""ADEP25 - tests de scripts/check_naive_datetime.py (cles d'exception = identites de contenu)."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_naive_datetime as cnd  # noqa: E402

MODELE = "from django.db import models\n\n\nclass Devis(models.Model):\n{pad}    cree_le = models.DateField(auto_now_add=True)\n"


def _arbre(tmp, pad_lignes):
    r = Path(tmp)
    d = r / "backend" / "django_core" / "apps" / "ventes"
    d.mkdir(parents=True)
    (d / "models.py").write_text(MODELE.format(pad="\n" * pad_lignes), encoding="utf-8")
    return r


def _scan(r):
    with mock.patch.object(cnd, "ROOT", r), \
            mock.patch.object(cnd, "DJANGO_CORE", r / "backend" / "django_core"), \
            mock.patch.object(cnd, "APPS_DIR", r / "backend" / "django_core" / "apps"):
        return cnd.check_datefield_timestamps()[1]


class CleContenuTests(unittest.TestCase):
    def test_ligne_697_ne_preautorise_plus(self):
        # Le champ fautif tombe pile sur l'ancienne ligne 697 de ventes/models.py.
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, 697 - 5)
            ligne = (r / "backend/django_core/apps/ventes/models.py").read_text(
                encoding="utf-8").splitlines().index("    cree_le = models.DateField(auto_now_add=True)") + 1
            self.assertEqual(ligne, 697)
            findings = _scan(r)
            self.assertTrue(any(code == "DATEFIELD_AUTO_NOW" for code, _m in findings), findings)

    def test_cle_orpheline_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, 0)
            findings = _scan(r)
            orphelines = [m for code, m in findings if code == "ORPHAN_ALLOWLIST_KEY"]
            self.assertTrue(orphelines, findings)

    def test_cle_vivante_autorise(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, 0)
            cle = "backend/django_core/apps/ventes/models.py::Devis.cree_le"
            with mock.patch.object(cnd, "DATEFIELD_AUTO_NOW_ALLOWLIST", {cle}), \
                    mock.patch.object(cnd, "TIMESTAMP_AS_DATEFIELD_ALLOWLIST", set()):
                self.assertEqual(_scan(r), [])

    def test_depot_reel_vert(self):
        self.assertEqual(cnd.check_naive_datetime()[1], [])
        self.assertEqual(cnd.check_datefield_timestamps()[1], [])


if __name__ == "__main__":
    unittest.main()
