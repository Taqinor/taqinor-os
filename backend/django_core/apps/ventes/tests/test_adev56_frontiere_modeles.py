"""ADEV56 (C-ADEV-027) — le code NON-modèle de ``apps.ventes`` n'importe
aucun ``models``/``views`` d'une autre app métier (crm, stock, installations,
sav) : il passe par leurs ``selectors.py`` / ``services.py`` (CLAUDE.md,
frontière inter-apps). Analyse AST (aucune base), qui NOMME chaque site.

Exclus : ``tests/``, ``migrations/``, ``management/`` et les fichiers
``tests_*.py`` à la racine de l'app (tests historiques).

Test-du-test : réintroduire ``from apps.stock.models import Produit`` dans
un module de ventes ⇒ ce test le nomme.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_adev56_frontiere_modeles"
"""
import ast
import re
from pathlib import Path

from django.test import SimpleTestCase

RACINE = Path(__file__).resolve().parents[1]
INTERDIT = re.compile(r'^apps\.(crm|stock|installations|sav)\.(models|views)\b')
DOSSIERS_EXCLUS = {'tests', 'migrations', 'management', '__pycache__'}


def _modules_non_test():
    for chemin in sorted(RACINE.rglob('*.py')):
        parties = set(chemin.relative_to(RACINE).parts[:-1])
        if parties & DOSSIERS_EXCLUS:
            continue
        if chemin.parent == RACINE and chemin.name.startswith('tests_'):
            continue
        yield chemin


def _sites_interdits(chemin):
    arbre = ast.parse(chemin.read_text(encoding='utf-8'), filename=str(chemin))
    sites = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom) and noeud.module \
                and noeud.level == 0 and INTERDIT.match(noeud.module):
            sites.append((noeud.lineno, noeud.module))
        elif isinstance(noeud, ast.Import):
            for alias in noeud.names:
                if INTERDIT.match(alias.name):
                    sites.append((noeud.lineno, alias.name))
    return sites


class FrontiereModelesTests(SimpleTestCase):
    def test_aucun_import_de_modeles_etrangers(self):
        sites = []
        for chemin in _modules_non_test():
            for ligne, module in _sites_interdits(chemin):
                sites.append(
                    f'{chemin.relative_to(RACINE).as_posix()}:{ligne} '
                    f'→ {module}')
        self.assertEqual(
            sites, [],
            'Import direct de models/views d\'une autre app métier dans '
            'ventes (passer par selectors.py / services.py) :\n'
            + '\n'.join(sites))

    def test_le_scanner_voit_un_import_interdit(self):
        """Test-du-test (sans toucher au dépôt) : le motif reconnaît bien
        un import interdit et laisse passer un sélecteur."""
        self.assertTrue(INTERDIT.match('apps.stock.models'))
        self.assertTrue(INTERDIT.match('apps.crm.views'))
        self.assertFalse(INTERDIT.match('apps.stock.selectors'))
        self.assertFalse(INTERDIT.match('apps.facturation.models'))
