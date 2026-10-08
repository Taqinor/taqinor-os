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
    same_company_fields = ('produit', 'voisine')

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

    def validate_voisine(self, voisine):
        return voisine
'''

SER_READ_ONLY = '''
from rest_framework import serializers
from .models import Ligne


class LigneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ligne
        fields = ['id', 'produit', 'referentiel', 'voisine']
        read_only_fields = ['produit', 'voisine']
'''


MODELS_USER = '''
from django.conf import settings
from django.db import models


class Tache(models.Model):
    company = models.ForeignKey('authentication.Company',
                                on_delete=models.CASCADE)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.CASCADE)
'''

SER_USER = '''
from rest_framework import serializers
from .models_x import Tache


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tache
        fields = ['id', 'responsable']
'''


class BaseArbre(unittest.TestCase):
    """Reconstruit un mini-dépôt et y pointe la garde."""

    def _monter(self, serializers_src, allowlist="", extra=None):
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
        # SPL72 — fichiers supplémentaires de l'app ``ao`` (scissions).
        for nom, contenu in (extra or {}).items():
            (apps / "ao" / nom).parent.mkdir(parents=True, exist_ok=True)
            (apps / "ao" / nom).write_text(contenu, encoding="utf-8")
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

    def test_fk_meme_app_non_bornee(self):
        # ASTK9 : une FK MEME-APP vers un modele a societe est une fuite
        # inter-societes au meme titre qu'une FK cross-app.
        self._monter(SER_NU)
        sites = cfs.collect_sites()
        champs = {c for _, _, c, _, couvert in sites if not couvert}
        self.assertIn("voisine", champs)
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("LigneSerializer.voisine", out)

    def test_fk_utilisateur_non_bornee(self):
        self._monter(SER_NU, extra={
            "models_x.py": MODELS_USER, "serializers_u.py": SER_USER})
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("UserSerializer.responsable", out)
        self.assertIn("authentication.CustomUser", out)

    def test_serializer_dans_views(self):
        self._monter(SER_VIDE, extra={"views/api.py": SER_X_NU})
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("views/api.py::LigneXSerializer.produit", out)

    def test_base_company_scoped_borne_toutes_les_relations(self):
        for base in ("CompanyScopedModelSerializer",
                     "CompanyScopedRelationsMixin, serializers.ModelSerializer"):
            src = SER_X_NU.replace("serializers.ModelSerializer", base)
            self._monter(SER_VIDE, extra={"views/api.py": src})
            code, out = self._main()
            self.assertEqual(code, 0, out)
            self._restaurer()


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
                      "::LigneSerializer.produit\n"
                      "backend/django_core/apps/ao/serializers.py"
                      "::LigneSerializer.voisine\n")
        code, out = self._main()
        self.assertEqual(code, 0, out)


MODELS_AO_SCINDE = '''
from django.db import models


class Ligne(models.Model):
    company = models.ForeignKey('authentication.Company',
                                on_delete=models.CASCADE)
'''

# ``Ligne`` est définie dans ``models_lignes.py`` (scission de models.py).
MODELS_LIGNES = '''
from django.db import models


class Ligne(models.Model):
    company = models.ForeignKey('authentication.Company',
                                on_delete=models.CASCADE)
    produit = models.ForeignKey('stock.Produit', on_delete=models.PROTECT)
'''

SER_VIDE = "from rest_framework import serializers\n"

SER_X_NU = '''
from rest_framework import serializers
from .models import Ligne


class LigneXSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ligne
        fields = ['id', 'produit']
'''

SER_BASE_MIXIN = '''
from rest_framework import serializers
from .models import Ligne


class _ScopeMixin:
    same_company_fields = ('produit',)


class LigneSerializer(_ScopeMixin, serializers.ModelSerializer):
    class Meta:
        model = Ligne
        fields = ['id', 'produit']
'''

SER_X_SOUS_CLASSE = '''
from rest_framework import serializers
from .models import Ligne
from .serializers import _ScopeMixin


class LigneXSerializer(_ScopeMixin, serializers.ModelSerializer):
    class Meta:
        model = Ligne
        fields = ['id', 'produit']
'''


class TestScissionSPL72(BaseArbre):
    """SPL72 — la garde suit les fichiers issus d'une scission (golden rouge
    avant le correctif : ces fichiers étaient SAUTÉS en silence)."""

    def test_fk_non_scopee_dans_serializers_x_est_refusee(self):
        self._monter(SER_VIDE, extra={"serializers_x.py": SER_X_NU})
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("serializers_x.py::LigneXSerializer.produit", out)

    def test_suffixe_serializers_est_decouvert(self):
        self._monter(SER_VIDE, extra={"x_serializers.py": SER_X_NU})
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("x_serializers.py::LigneXSerializer.produit", out)

    def test_modele_defini_dans_models_x_est_vu(self):
        tmp = self._monter(SER_NU, extra={"models_lignes.py": MODELS_LIGNES})
        # ``models.py`` ne définit plus la FK : seule ``models_lignes.py`` la porte.
        (tmp / "backend" / "django_core" / "apps" / "ao" / "models.py"
         ).write_text(MODELS_AO_SCINDE, encoding="utf-8")
        sites = cfs.collect_sites()
        self.assertIn("produit", {c for _, _, c, _, _ in sites})

    def test_sous_classe_couverte_par_un_mixin_d_un_autre_fichier(self):
        self._monter(SER_BASE_MIXIN,
                     extra={"serializers_x.py": SER_X_SOUS_CLASSE})
        code, out = self._main()
        self.assertEqual(code, 0, out)
        sites = cfs.collect_sites()
        self.assertTrue(any(cls == "LigneXSerializer" and couvert
                            for _, cls, _, _, couvert in sites), sites)


SER_SCOPED_RELATIONS = '''
from rest_framework import serializers
from .models import Ligne


class _CompanyScopedRelationsMixin:
    scoped_relations: tuple = ()


class LigneSerializer(_CompanyScopedRelationsMixin, serializers.ModelSerializer):
    scoped_relations = ('produit', 'voisine')

    class Meta:
        model = Ligne
        fields = ['id', 'produit', 'referentiel', 'voisine']
'''


class TestBornesDeclarees(BaseArbre):
    """ALEA42 : `scoped_relations` borne ; une ligne d'allowlist inutile échoue."""

    def test_scoped_relations_reconnu(self):
        self._monter(SER_SCOPED_RELATIONS)
        code, out = self._main()
        self.assertEqual(code, 0, out)
        sites = cfs.collect_sites()
        self.assertTrue(sites and all(couvert for *_, couvert in sites), sites)

    def test_ligne_allowlist_inutile_echoue(self):
        self._monter(
            SER_SCOPED_RELATIONS,
            allowlist="backend/django_core/apps/ao/serializers.py"
                      "::LigneSerializer.produit\n")
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("ligne d'allowlist inutile : "
                      "backend/django_core/apps/ao/serializers.py"
                      "::LigneSerializer.produit", out)
        self.assertIn("la retirer", out)

    def test_ligne_allowlist_utile_reste_toleree(self):
        self._monter(
            SER_NU,
            allowlist="backend/django_core/apps/ao/serializers.py"
                      "::LigneSerializer.produit\n"
                      "backend/django_core/apps/ao/serializers.py"
                      "::LigneSerializer.voisine\n")
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
