"""AMOT73 - scripts/check_taux_tva_repli.py."""
import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_taux_tva_repli as garde  # noqa: E402 — après sys.path/setup() (D-ENF22)


class FixturesTests(unittest.TestCase):
    def test_or_vingt_rouge(self):
        self.assertEqual(len(garde.trouver("x = devis.taux_tva or Decimal(20)\n")), 1)
        self.assertEqual(len(garde.trouver("x = taux_tva or 20\n")), 1)
        self.assertEqual(len(garde.trouver("x = tva or 20.0\n")), 1)
        self.assertEqual(len(garde.trouver("x = d.get('taux_tva', 20) or 20\n")), 1)

    def test_is_none_vert(self):
        src = "x = 20 if devis.taux_tva is None else devis.taux_tva\n"
        self.assertEqual(garde.trouver(src), [])

    def test_or_zero_tolere(self):
        self.assertEqual(garde.trouver("x = facture.taux_tva or 0\n"), [])
        self.assertEqual(garde.trouver("x = Decimal(facture.taux_tva or 0)\n"), [])
        self.assertEqual(garde.trouver("x = tva or Decimal('0')\n"), [])

    def test_autre_nom_ignore(self):
        self.assertEqual(garde.trouver("x = remise or 20\n"), [])

    def test_migrations_ignorees(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        (tmp / "migrations").mkdir()
        (tmp / "migrations" / "0001.py").write_text("x = taux_tva or 20\n")
        (tmp / "mod.py").write_text("y = 1\n")
        noms = [p.name for p in garde._fichiers(tmp)]
        self.assertEqual(noms, ["mod.py"])


class DepotTests(unittest.TestCase):
    def _lancer(self):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = garde.main([])
        return code, sortie.getvalue()

    def test_depot_vert(self):
        code, sortie = self._lancer()
        self.assertEqual(code, 0, sortie)

    def test_test_du_test_motif_reintroduit_nomme(self):
        # AMOT77 — le site moteur est corrigé : le motif est réintroduit
        # dans un arbre temporaire, la garde doit le nommer.
        import tempfile
        from unittest import mock
        tmp = Path(tempfile.mkdtemp())
        ventes = tmp / "apps" / "ventes"
        ventes.mkdir(parents=True)
        (ventes / "moteur.py").write_text(
            "T = float(data.get('taux_tva', 20) or 20)\n", encoding="utf-8")
        with mock.patch.object(garde, "ROOT", tmp), mock.patch.object(garde, "VENTES", ventes):
            code, sortie = self._lancer()
        self.assertEqual(code, 1)
        self.assertIn("moteur.py", sortie)


if __name__ == "__main__":
    unittest.main()
