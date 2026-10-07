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


def _findings(src, serializer_names=()):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'module.py'
        path.write_text(src, encoding='utf-8')
        # serializer_names fige : jamais de balayage du depot dans ces tests.
        return guard.check_file(path, serializer_names=serializer_names)


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


SERIALIZER_SAVE = '''
class MouvementSerializer(serializers.ModelSerializer):
    class Meta:
        model = MouvementStock
        fields = '__all__'


def creer(data):
    ser = MouvementSerializer(data=data)
    ser.is_valid(raise_exception=True)
    ser.save()
'''

VUE_SERIALIZER_SAVE = '''
class MouvementViewSet(viewsets.ModelViewSet):
    serializer_class = MouvementSerializer

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
'''

SERIALIZER_SANS_SAVE = '''
class MouvementSerializer(serializers.ModelSerializer):
    class Meta:
        model = MouvementStock
        fields = '__all__'


def lire(data):
    ser = MouvementSerializer(data=data)
    return ser.is_valid()


def autre(data):
    ser = ProduitSerializer(data=data)
    ser.save()
'''

ECRITURE_STOCK = '''
def corriger(produit):
    produit.quantite_stock = 5
    produit.save(update_fields=['quantite_stock'])
'''

ECRITURE_STOCK_UPDATE = '''
def corriger(qs):
    qs.update(quantite_stock=0)
    produit.quantite_stock += 1
'''

ECRITURE_DANS_SERVICE = '''
def record_stock_movement(produit, quantite_apres):
    produit.quantite_stock = quantite_apres
    produit.save(update_fields=['quantite_stock'])
'''

LECTURE_STOCK = '''
def lire(produit):
    return produit.quantite_stock + 1
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

    def test_serializer_save_detecte(self):
        self.assertEqual(len(_findings(SERIALIZER_SAVE)), 1)
        self.assertEqual(len(_findings(VUE_SERIALIZER_SAVE, ['MouvementSerializer'])), 1)

    def test_serializer_sans_save_ou_autre_modele_accepte(self):
        self.assertEqual(_findings(SERIALIZER_SANS_SAVE), [])

    def test_ecriture_directe_quantite_stock(self):
        # affectation + update_fields : 2 sites
        self.assertEqual(len(_findings(ECRITURE_STOCK)), 2)
        # .update(quantite_stock=) + augmented assignment : 2 sites
        self.assertEqual(len(_findings(ECRITURE_STOCK_UPDATE)), 2)

    def test_ecriture_dans_le_service_et_lecture_acceptees(self):
        self.assertEqual(_findings(ECRITURE_DANS_SERVICE), [])
        self.assertEqual(_findings(LECTURE_STOCK), [])


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
