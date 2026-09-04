"""Tests AUD601 — scripts/check_fk_scoping.py.

Pure stdlib (unittest), no Django. Run:
    python -m unittest scripts.tests.test_check_fk_scoping -v
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_fk_scoping as cfs  # noqa: E402


MODELS_STOCK = '''
from django.db import models


class Produit(models.Model):
    company = models.ForeignKey('authentication.Company',
                                on_delete=models.CASCADE)
    nom = models.CharField(max_length=50)


class Referentiel(models.Model):
    """Table PARTAGÉE, sans société — rien à valider."""
    code = models.CharField(max_length=10)
'''

MODELS_AO = '''
from django.db import models


class Ligne(models.Model):
    company = models.ForeignKey('authentication.Company',
                                on_delete=models.CASCADE)
    produit = models.ForeignKey('stock.Produit', on_delete=models.PROTECT)
    referentiel = models.ForeignKey('stock.Referentiel',
                                    on_delete=models.PROTECT)
    voisine = models.ForeignKey('ao.Ligne', on_delete=models.CASCADE)
'''

SER_NU = '''
from rest_framework import serializers
from .models import Ligne


class LigneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ligne
        fields = ['id', 'produit', 'referentiel', 'voisine']
'''

SER_MIXIN = '''
from rest_framework import serializers
from .models import Ligne


class LigneSerializer(serializers.ModelSerializer):
    same_company_fields = ('produit',)

    class Meta:
        model = Ligne
        fields = ['id', 'produit', 'referentiel', 'voisine']
'''

SER_VALIDATE = '''
from rest_framework import serializers
from .models import Ligne


class LigneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ligne
        fields = ['id', 'produit', 'referentiel', 'voisine']

    def validate_produit(self, produit):
        return produit
'''

SER_READ_ONLY = '''
from rest_framework import serializers
from .models import Ligne


class LigneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ligne
        fields = ['id', 'produit', 'referentiel', 'voisine']
        read_only_fields = ['produit']
'''


class BaseArbre(unittest.TestCase):
    """Reconstruit un mini-dépôt et y pointe la garde."""

    def _monter(self, serializers_src, allowlist=""):
        tmp = Path(tempfile.mkdtemp())
        apps = tmp / "backend" / "django_core" / "apps"
        (apps / "stock").mkdir(parents=True)
        (apps / "ao").mkdir(parents=True)
        (tmp / "scripts").mkdir(parents=True)
        (apps / "stock" / "models.py").write_text(MODELS_STOCK,
                                                  encoding="utf-8")
        (apps / "ao" / "models.py").write_text(MODELS_AO, encoding="utf-8")
        (apps / "ao" / "serializers.py").write_text(serializers_src,
                                                    encoding="utf-8")
        allow = tmp / "scripts" / "fk_scoping_allow.txt"
        allow.write_text(allowlist, encoding="utf-8")

        self._sauvegarde = (cfs.ROOT, cfs.DJANGO_CORE, cfs.APPS_DIR,
                            cfs.ALLOWLIST_PATH)
        cfs.ROOT = tmp
        cfs.DJANGO_CORE = tmp / "backend" / "django_core"
        cfs.APPS_DIR = apps
        cfs.ALLOWLIST_PATH = allow
        self.addCleanup(self._restaurer)
        return tmp

    def _restaurer(self):
        (cfs.ROOT, cfs.DJANGO_CORE, cfs.APPS_DIR,
         cfs.ALLOWLIST_PATH) = self._sauvegarde

    @staticmethod
    def _main(argv=()):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cfs.main(list(argv))
        return code, buf.getvalue()


class TestDetection(BaseArbre):
    def test_fk_cross_app_non_validee_est_refusee(self):
        self._monter(SER_NU)
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("LigneSerializer.produit", out)

    def test_fk_vers_table_sans_societe_ignoree(self):
        self._monter(SER_NU)
        sites = cfs.collect_sites()
        champs = {c for _, _, c, _, _ in sites}
        self.assertNotIn("referentiel", champs)

    def test_fk_meme_app_ignoree(self):
        self._monter(SER_NU)
        sites = cfs.collect_sites()
        champs = {c for _, _, c, _, _ in sites}
        self.assertNotIn("voisine", champs)


class TestCouverture(BaseArbre):
    def test_same_company_fields_couvre(self):
        self._monter(SER_MIXIN)
        code, out = self._main()
        self.assertEqual(code, 0, out)

    def test_validate_champ_couvre(self):
        self._monter(SER_VALIDATE)
        code, out = self._main()
        self.assertEqual(code, 0, out)

    def test_read_only_fields_sort_du_perimetre(self):
        self._monter(SER_READ_ONLY)
        sites = cfs.collect_sites()
        self.assertEqual(sites, [])

    def test_allowlist_tolere_un_site_pre_existant(self):
        self._monter(
            SER_NU,
            allowlist="# constaté, pas approuvé\n"
                      "backend/django_core/apps/ao/serializers.py"
                      "::LigneSerializer.produit\n")
        code, out = self._main()
        self.assertEqual(code, 0, out)


class TestDepotReel(unittest.TestCase):
    """Le dépôt RÉEL doit rester vert (allowlist à jour)."""

    def test_depot_vert(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cfs.main([])
        self.assertEqual(code, 0, buf.getvalue())


if __name__ == "__main__":
    unittest.main()
