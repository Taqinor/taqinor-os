"""Tests AANA47 — check_fk_scoping : M2M, FK vers utilisateur/role, et tout
module qui definit un ModelSerializer (pas seulement serializers*.py).

Stdlib pure (unittest), sans Django. Run:
    python -m unittest scripts.tests.test_check_fk_scoping_m2m -v
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

MODELS_REPORTING = '''
from django.conf import settings
from django.db import models


class Alerte(models.Model):
    company = models.ForeignKey('authentication.Company',
                                on_delete=models.CASCADE)
    destinataires_utilisateurs = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True)
    proprietaire = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.CASCADE)
    role = models.ForeignKey('roles.Role', on_delete=models.PROTECT)
'''

SER_NU = '''
from rest_framework import serializers
from .models import Alerte


class AlerteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alerte
        fields = ['id', 'destinataires_utilisateurs', 'proprietaire', 'role']
'''

SER_COUVERT = '''
from rest_framework import serializers
from .models import Alerte


class AlerteSerializer(serializers.ModelSerializer):
    same_company_fields = ('destinataires_utilisateurs', 'proprietaire')

    class Meta:
        model = Alerte
        fields = ['id', 'destinataires_utilisateurs', 'proprietaire']
'''


class Base(unittest.TestCase):
    def _monter(self, fichiers, allowlist=""):
        tmp = Path(tempfile.mkdtemp())
        apps = tmp / "backend" / "django_core" / "apps"
        (apps / "reporting").mkdir(parents=True)
        (tmp / "scripts").mkdir(parents=True)
        (apps / "reporting" / "models.py").write_text(
            MODELS_REPORTING, encoding="utf-8")
        for nom, contenu in fichiers.items():
            cible = apps / "reporting" / nom
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(contenu, encoding="utf-8")
        allow = tmp / "scripts" / "fk_scoping_allow.txt"
        allow.write_text(allowlist, encoding="utf-8")
        sauve = (cfs.ROOT, cfs.DJANGO_CORE, cfs.APPS_DIR, cfs.ALLOWLIST_PATH)
        cfs.ROOT = tmp
        cfs.DJANGO_CORE = tmp / "backend" / "django_core"
        cfs.APPS_DIR = apps
        cfs.ALLOWLIST_PATH = allow

        def restaurer():
            (cfs.ROOT, cfs.DJANGO_CORE, cfs.APPS_DIR,
             cfs.ALLOWLIST_PATH) = sauve
        self.addCleanup(restaurer)

    @staticmethod
    def _main():
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cfs.main([])
        return code, buf.getvalue()


class TestM2mUtilisateur(Base):
    def test_m2m_utilisateur_detecte(self):
        self._monter({"serializers.py": SER_NU})
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("AlerteSerializer.destinataires_utilisateurs", out)
        self.assertIn("AlerteSerializer.proprietaire", out)
        self.assertIn("AlerteSerializer.role", out)
        self.assertIn("authentication.CustomUser", out)
        self.assertIn("roles.Role", out)

    def test_same_company_fields_couvre_m2m_et_user(self):
        self._monter({"serializers.py": SER_COUVERT})
        code, out = self._main()
        self.assertEqual(code, 0, out)

    def test_module_hors_serializers_glob_est_balaye(self):
        # Un ModelSerializer defini dans views/api.py n'echappe plus.
        self._monter({"views/api.py": SER_NU})
        code, out = self._main()
        self.assertEqual(code, 1, out)
        self.assertIn("views/api.py::AlerteSerializer", out)

    def test_module_de_tests_reste_ignore(self):
        self._monter({"tests/ser.py": SER_NU, "test_x.py": SER_NU})
        code, out = self._main()
        self.assertEqual(code, 0, out)

    def test_allowlist_tolere_le_site(self):
        base = "backend/django_core/apps/reporting/serializers.py::"
        champs = ("destinataires_utilisateurs", "proprietaire", "role")
        self._monter(
            {"serializers.py": SER_NU},
            allowlist="\n".join(base + "AlerteSerializer." + c
                                for c in champs) + "\n")
        code, out = self._main()
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
