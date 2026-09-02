"""SOL4 — la garde de clôture anti-recouplage tourne, et elle MORD.

Deux choses à prouver, pas une :

1. le dépôt est propre — aucune app gardée de l'édition solaire n'importe, ne
   référence en chaîne, ni ne fait dépendre une migration d'une app parquée ;
2. la garde DÉTECTE réellement ces trois formes d'arête — une garde verte qui
   ne sait rien voir ne protège rien (elle serait verte pour toujours).
"""
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_RACINE = Path(settings.BASE_DIR).resolve().parent.parent
_SCRIPT = _RACINE / 'scripts' / 'check_editions_decouplage.py'
# Le dépôt complet n'est pas toujours monté (image qui n'expose que
# backend/django_core) : la garde reste alors couverte par son step CI dédié.
_scripts_montes = unittest.skipUnless(
    _SCRIPT.exists(), f'scripts/ non monté dans cet environnement ({_SCRIPT})')


def _charger_garde():
    spec = importlib.util.spec_from_file_location('_sol4_garde', _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@_scripts_montes
class GardeDecouplageTests(SimpleTestCase):
    def test_depot_sans_arete_vers_une_app_parquee(self):
        res = subprocess.run(
            [sys.executable, str(_SCRIPT), '--edition', 'solar'],
            cwd=str(_RACINE), capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=600)
        self.assertEqual(
            res.returncode, 0,
            f'arête(s) de recouplage détectée(s) :\n{res.stdout}\n{res.stderr}')

    def test_edition_complete_ne_parque_rien(self):
        res = subprocess.run(
            [sys.executable, str(_SCRIPT), '--edition', 'full'],
            cwd=str(_RACINE), capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=600)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


@_scripts_montes
class GardeDetecteLesTroisFormesTests(SimpleTestCase):
    """La garde doit MORDRE sur chacune des trois formes d'arête."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.garde = _charger_garde()

    def test_detecte_un_import(self):
        aretes = self.garde._aretes_imports(
            Path('faux.py'),
            'def f():\n    from apps.sante.services import x\n',
            {'sante': 'apps.sante'})
        self.assertEqual(len(aretes), 1)
        self.assertEqual(aretes[0][1], 'IMPORT')
        self.assertIn('apps.sante.services', aretes[0][3])

    def test_detecte_un_import_module_level(self):
        aretes = self.garde._aretes_imports(
            Path('faux.py'), 'import apps.mrp.models\n', {'mrp': 'apps.mrp'})
        self.assertEqual(len(aretes), 1)

    def test_ignore_une_app_gardee_au_nom_proche(self):
        aretes = self.garde._aretes_imports(
            Path('faux.py'), 'import apps.mrpbis.models\n', {'mrp': 'apps.mrp'})
        self.assertEqual(aretes, [])

    def test_detecte_une_dependance_de_migration(self):
        source = (
            'class Migration:\n'
            "    dependencies = [('qhse', '0056_x'), ('sante', '0019_y')]\n")
        aretes = self.garde._aretes_migrations(
            Path('0057_x.py'), source, {'sante'})
        self.assertEqual(len(aretes), 1)
        self.assertEqual(aretes[0][1], 'MIGRATION')
        self.assertIn('sante', aretes[0][3])

    def test_detecte_une_reference_de_modele_en_chaine(self):
        aretes = self.garde._aretes_refs_chaine(
            Path('models.py'),
            "    cycle = models.ForeignKey('sante.CycleSterilisation')\n",
            {'sante'})
        self.assertEqual(len(aretes), 1)
        self.assertEqual(aretes[0][1], 'REF_CHAINE')

    def test_allowlist_sans_numero_de_ligne(self):
        """L'allowlist est indexée (fichier, jeton) — jamais file:line."""
        entrees = self.garde.charger_allowlist()
        self.assertTrue(entrees, 'allowlist vide : format à revérifier')
        for cle, justification in entrees.items():
            fichier, jeton = cle
            self.assertNotIn(
                ':', fichier.rsplit('/', 1)[-1].replace('.py', ''),
                f'entrée d\'allowlist avec numéro de ligne : {cle}')
            self.assertTrue(jeton)
            self.assertTrue(
                justification,
                f'entrée d\'allowlist sans justification : {cle}')
