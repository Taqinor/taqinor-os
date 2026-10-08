"""Scission du moteur de devis (SPL162 → SPL169) — test STRUCTUREL.

Complément de la preuve comportementale (golden SPL160, qui exécute le vrai
code) : chaque nom déplacé est DÉFINI dans son nouveau module et ne l'est
plus dans le module source (analyse AST, aucun import Django). Étendu par
chaque tâche SPL de la scission. Aucun jumeau : une seule définition.
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

MOTEUR = Path(__file__).resolve().parents[1] / 'quote_engine'


def definis(nom_fichier):
    """Noms DÉFINIS au niveau module (def / class / affectation / import)."""
    arbre = ast.parse((MOTEUR / nom_fichier).read_text(encoding='utf-8'))
    noms = {}
    for n in arbre.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            noms[n.name] = 'def'
        elif isinstance(n, ast.Assign):
            for cible in n.targets:
                if isinstance(cible, ast.Name):
                    noms[cible.id] = 'affectation'
        elif isinstance(n, ast.ImportFrom):
            for alias in n.names:
                noms[alias.asname or alias.name] = 'import:%s' % (
                    n.module or '.')
    return noms


#: SPL162 — helpers de classement de ligne : builder.py → lignes_classement.py.
SPL162 = (
    '_WATT_RE', '_DEFAULT_WATT', '_BRAND_TOKENS', '_parse_marque',
    '_parse_watt', '_WATT_FICHE_TYPES', '_fiche_watt', '_is_battery',
    '_KWH_RE', '_battery_kwh_from_items', '_cout_onduleur',
    '_LigneArgentPdf', '_is_hybrid_inverter', '_is_reseau_inverter',
    '_is_offgrid_inverter', '_PANEL_MODULE_QUALIFIERS', '_PANEL_BRANDS',
    '_is_panel', '_is_inverter', '_is_smart_meter', '_is_wifi_dongle',
    '_item_classement', '_item_marque', '_line_to_item',
    'puissance_panneaux_lignes', 'panneaux_et_watt_lu',
)


class Spl162LignesClassementTests(SimpleTestCase):

    def test_chaque_nom_defini_dans_lignes_classement(self):
        cible = definis('lignes_classement.py')
        for nom in SPL162:
            with self.subTest(nom=nom):
                self.assertIn(cible.get(nom), ('def', 'affectation'))

    def test_aucun_nom_encore_defini_dans_builder(self):
        source = definis('builder.py')
        for nom in SPL162:
            with self.subTest(nom=nom):
                # Lié par import (usage propre ou ré-export) : permis ;
                # DÉFINI (def / affectation) : jumeau interdit.
                self.assertNotIn(source.get(nom), ('def', 'affectation'))
                if nom in source:
                    self.assertEqual(source[nom], 'import:lignes_classement')

    def test_lignes_classement_n_importe_jamais_builder(self):
        texte = (MOTEUR / 'lignes_classement.py').read_text(encoding='utf-8')
        arbre = ast.parse(texte)
        for n in ast.walk(arbre):
            if isinstance(n, ast.ImportFrom):
                self.assertNotIn('builder', n.module or '')
                self.assertNotIn('builder', [a.name for a in n.names])
            if isinstance(n, ast.Import):
                self.assertFalse(any('builder' in a.name for a in n.names))
        # Les imports ``utils.options`` restent LOCAUX (cycle).
        tete = [n for n in arbre.body if isinstance(n, ast.ImportFrom)]
        self.assertFalse(any('utils.options' in (n.module or '')
                             for n in tete))
