"""ASEC46 -- check_machine_etats_statut_readonly.py voit les serialiseurs
declares par ``Meta.exclude`` (champs = modele moins l'exclusion).

Pur stdlib, mini-depot temporaire. Lancer :
    python -m unittest scripts.tests.test_check_machine_etats_statut_readonly_exclude -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_machine_etats_statut_readonly as garde  # noqa: E402

MACHINE = "from .models import Dossier\n"
MODELS = '''
from django.db import models


class Dossier(models.Model):
    statut = models.CharField(max_length=20)
    nom = models.CharField(max_length=20)
'''
SER_EXCLUDE_OUVERT = '''
from rest_framework import serializers
from .models import Dossier


class DossierWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dossier
        exclude = ['nom']
'''
SER_EXCLUDE_FERME = '''
from rest_framework import serializers
from .models import Dossier


class DossierWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dossier
        exclude = ['statut']
'''


class StatutViaExcludeTests(unittest.TestCase):
    def _divergences(self, serializer_src):
        tmp = Path(tempfile.mkdtemp())
        apps = tmp / "backend" / "django_core" / "apps"
        app = apps / "dossiers"
        app.mkdir(parents=True)
        (app / "machine_etats.py").write_text(MACHINE, encoding="utf-8")
        (app / "models.py").write_text(MODELS, encoding="utf-8")
        (app / "serializers.py").write_text(serializer_src, encoding="utf-8")
        sauvegarde = (garde.ROOT, garde.APPS_DIR, garde.ALLOWLIST_PATH)
        garde.ROOT, garde.APPS_DIR = tmp, apps
        garde.ALLOWLIST_PATH = tmp / "absente.txt"
        self.addCleanup(lambda: setattr(garde, "ROOT", sauvegarde[0]))
        self.addCleanup(lambda: setattr(garde, "APPS_DIR", sauvegarde[1]))
        self.addCleanup(lambda: setattr(garde, "ALLOWLIST_PATH", sauvegarde[2]))
        return garde.divergences()

    def test_statut_via_exclude_detecte(self):
        trouvees = self._divergences(SER_EXCLUDE_OUVERT)
        self.assertEqual(len(trouvees), 1, trouvees)
        self.assertIn("DossierWriteSerializer", trouvees[0])

    def test_exclude_statut_est_une_porte_fermee(self):
        self.assertEqual(self._divergences(SER_EXCLUDE_FERME), [])


if __name__ == "__main__":
    unittest.main()
