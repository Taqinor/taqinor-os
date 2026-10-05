"""ACAL330 (C-ACAL-145, C-ACAL-063) — ``battery_storage_sizing`` (jumeau mort
de ``solar_design.py``) et le rendement aller-retour de repli
``_BATTERY_DEFAULT_ROUND_TRIP`` n'existent plus ; les trois hypothèses
batterie que ``apps/calepinage/services/batterie.py`` relit RESTENT ; aucune
fonction publique de ``solar_design`` ne vit sans appelant de production.

``SimpleTestCase`` : lecture de modules et graphe d'appels par AST.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_solar_design_sans_orphelin"
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes import solar_design as sd

RACINE = Path(__file__).resolve().parents[3]
SOURCE = RACINE / 'apps' / 'ventes' / 'solar_design.py'

#: Fonctions publiques SANS appelant de production gardées SCIEMMENT, avec
#: leur raison (hors périmètre d'ACAL330 — à statuer par leur propre tâche).
#: Constat du build ACAL330 (graphe AST du 05/10/2026) : ces six fonctions
#: n'ont plus d'appelant de production (seuls des tests et des docstrings les
#: citent). Leur sort n'est PAS tranché par ACAL330 (qui ne supprime que
#: ``battery_storage_sizing``) : elles sont gelées ici — toute NOUVELLE
#: orpheline rougit ce test.
_A_STATUER = 'orpheline constatée au build ACAL330, hors périmètre (à statuer)'
ALLOWLISTE = {
    'compare_scenarios': 'FG — ' + _A_STATUER,
    'ev_charger_sizing': 'FG — ' + _A_STATUER,
    'generate_boq': 'remplacée par core.electrique.nomenclature — '
                    + _A_STATUER,
    'load_curve_from_xlsx': 'FG — ' + _A_STATUER,
    'match_inverter': 'FG — ' + _A_STATUER,
    'optimize_orientation': 'FG249 — ' + _A_STATUER,
}


def _fonctions_publiques():
    arbre = ast.parse(SOURCE.read_text(encoding='utf-8'))
    return sorted(noeud.name for noeud in arbre.body
                  if isinstance(noeud, ast.FunctionDef)
                  and not noeud.name.startswith('_'))


def _noms_cites_en_production():
    """Tous les identifiants / attributs cités par le code de PRODUCTION
    (hors tests, hors migrations, hors ``solar_design.py`` lui-même)."""
    cites = set()
    for chemin in RACINE.rglob('*.py'):
        morceaux = chemin.parts
        if ('tests' in morceaux or 'migrations' in morceaux
                or chemin.name.startswith('test_') or chemin == SOURCE
                or '__pycache__' in morceaux):
            continue
        try:
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Name):
                cites.add(noeud.id)
            elif isinstance(noeud, ast.Attribute):
                cites.add(noeud.attr)
            elif isinstance(noeud, ast.alias):
                cites.add(noeud.asname or noeud.name.split('.')[-1])
                cites.add(noeud.name.split('.')[-1])
    return cites


class SolarDesignSansOrphelin(SimpleTestCase):

    def test_battery_storage_sizing_et_le_rendement_de_repli_n_existent_plus(self):
        self.assertFalse(hasattr(sd, 'battery_storage_sizing'))
        self.assertFalse(hasattr(sd, '_BATTERY_DEFAULT_ROUND_TRIP'))
        # Les trois hypothèses de référence ÉTIQUETÉES restent (CALX286).
        for nom in ('_BATTERY_DEFAULT_DOD', '_BATTERY_BACKUP_PEAK_FACTOR',
                    '_BATTERY_DEFAULT_NIGHT_FRACTION'):
            self.assertTrue(hasattr(sd, nom), nom)
        from apps.calepinage.services import batterie  # noqa: F401 — importable

    def test_aucune_fonction_publique_de_solar_design_sans_appelant_de_production(self):
        cites = _noms_cites_en_production()
        orphelines = [nom for nom in _fonctions_publiques()
                      if nom not in cites and nom not in ALLOWLISTE]
        self.assertEqual(
            orphelines, [],
            'fonctions publiques de solar_design sans appelant de production : '
            '%r' % orphelines)

    def test_l_allowliste_ne_garde_que_des_fonctions_existantes(self):
        publiques = set(_fonctions_publiques())
        for nom in ALLOWLISTE:
            self.assertIn(nom, publiques, nom)
