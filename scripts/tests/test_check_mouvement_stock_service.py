"""Tests AUD223 — scripts/check_mouvement_stock_service.py.

Stdlib pur (unittest), sans Django — miroir de la garde DB-free. Run :
    python -m unittest scripts.tests.test_check_mouvement_stock_service -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_mouvement_stock_service as guard  # noqa: E402


def _findings(src):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'module.py'
        path.write_text(src, encoding='utf-8')
        return guard.check_file(path)


CREATE_DIRECT = '''
def sortir(produit):
    MouvementStock.objects.create(
        company=produit.company, produit=produit, quantite=1,
        quantite_avant=1, quantite_apres=0)
'''

CREATE_VIA_SERVICE = '''
def sortir(produit):
    record_stock_movement(
        company=produit.company, produit=produit, quantite=1,
        quantite_avant=1, quantite_apres=0, type_mouvement='sortie',
        reference='X', note='', created_by=None)
'''

INSTANCIATION_NUE = '''
def sortir(produit):
    m = MouvementStock(produit=produit, quantite=1)
    m.save()
'''

BULK_CREATE = '''
def sortir(produits):
    MouvementStock.objects.bulk_create([])
'''

AUTRE_MODELE = '''
def creer(produit):
    LigneInventaire.objects.create(produit=produit)
    MouvementRebut.objects.create(produit=produit)
'''

IMPORT_QUALIFIE = '''
def sortir(produit):
    models.MouvementStock.objects.create(produit=produit)
'''


class DetectionTests(unittest.TestCase):
    def test_create_direct_est_signale(self):
        self.assertEqual(len(_findings(CREATE_DIRECT)), 1)

    def test_appel_au_service_est_accepte(self):
        self.assertEqual(_findings(CREATE_VIA_SERVICE), [])

    def test_instanciation_nue_est_signalee(self):
        self.assertEqual(len(_findings(INSTANCIATION_NUE)), 1)

    def test_bulk_create_est_signale(self):
        self.assertEqual(len(_findings(BULK_CREATE)), 1)

    def test_un_autre_modele_nest_pas_signale(self):
        self.assertEqual(_findings(AUTRE_MODELE), [])

    def test_acces_qualifie_est_signale(self):
        self.assertEqual(len(_findings(IMPORT_QUALIFIE)), 1)


class PerimetreTests(unittest.TestCase):
    def test_les_tests_et_migrations_sont_hors_perimetre(self):
        for chemin in ('apps/stock/test_x.py', 'apps/stock/tests_fg.py',
                       'apps/stock/tests.py',
                       'apps/stock/tests/test_y.py',
                       'apps/stock/migrations/0001_init.py'):
            self.assertTrue(guard._is_test_path(Path(chemin)), chemin)

    def test_le_code_de_production_est_dans_le_perimetre(self):
        for chemin in ('apps/stock/services.py',
                       'apps/stock/views/produit.py',
                       'apps/dataimport/services.py'):
            self.assertFalse(guard._is_test_path(Path(chemin)), chemin)


class AllowlistTests(unittest.TestCase):
    def test_le_service_lui_meme_est_dans_l_allowlist(self):
        allow = guard._load_allowlist()
        self.assertIn('backend/django_core/apps/stock/services.py', allow)

    def test_le_depot_est_propre(self):
        """La garde passe sur le dépôt réel (aucun site hors allowlist)."""
        self.assertEqual(guard.main([]), 0)


if __name__ == '__main__':
    unittest.main()
