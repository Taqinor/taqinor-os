# -*- coding: utf-8 -*-
"""ACAL329 — aucun symbole mort du modèle « PVGIS applique les pertes ».

LE CONSTAT (C-ACAL-145)
-----------------------
``production.production_du_layout`` (un appel PVGIS ``pvcalculation=1`` par
pan, pertes passées en ``loss``), ``ClientPvgis.serie_horaire`` et
``pertes.politique_du_calepinage`` n'avaient plus AUCUN appelant hors tests :
la production du module a UN producteur, ``services/chaine_pertes.py``, qui
lit l'irradiance NUE (``serie_irradiance``) et applique chaque poste. Le
motif « non simulable » de ``GET pertes/`` affirmait encore le contraire
(« le module passe TOUJOURS à PVGIS la somme explicite de ses postes »).

Ce qui est prouvé ici (AST, sans base, sans réseau) :

* chaque fonction/classe PUBLIQUE de ``production.py`` et ``pvgis_serie.py``
  (méthodes publiques de ``ClientPvgis`` comprises) est NOMMÉE par au moins
  un fichier non-test du backend, autre que son module ;
* ``politique_du_calepinage`` n'existe plus dans ``pertes.py`` ;
* le motif non simulable ne parle plus de pertes passées à PVGIS.

Run :
    python manage.py test apps.calepinage.tests.test_acal_production_symboles_morts
"""
from __future__ import annotations

import ast
import pathlib
import unittest

BACKEND = pathlib.Path(__file__).resolve().parents[3]
SERVICES = BACKEND / 'apps' / 'calepinage' / 'services'
MODULES = (SERVICES / 'production.py', SERVICES / 'pvgis_serie.py')

#: Symboles encore présents dont la SUPPRESSION appartient à une autre tâche
#: — la tâche nommée retire l'entrée dans le commit qui supprime le symbole.
EN_ATTENTE = {'vider_le_cache': 'ACAL293'}


def _arbre(chemin):
    return ast.parse(chemin.read_text(encoding='utf-8'))


def _symboles_publics(chemin):
    noms = []
    for noeud in _arbre(chemin).body:
        if not isinstance(noeud, (ast.FunctionDef, ast.ClassDef)):
            continue
        if not noeud.name.startswith('_'):
            noms.append(noeud.name)
        if isinstance(noeud, ast.ClassDef) and noeud.name == 'ClientPvgis':
            noms.extend(enfant.name for enfant in noeud.body
                        if isinstance(enfant, ast.FunctionDef)
                        and not enfant.name.startswith('_'))
    return noms


def _est_un_test(chemin):
    morceaux = chemin.relative_to(BACKEND).parts
    return ('tests' in morceaux or chemin.name.startswith('test')
            or chemin.name.startswith('tests_'))


def _noms_cites(chemin):
    try:
        arbre = _arbre(chemin)
    except (SyntaxError, UnicodeDecodeError):
        return set()
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name):
            noms.add(noeud.id)
        elif isinstance(noeud, ast.Attribute):
            noms.add(noeud.attr)
        elif isinstance(noeud, ast.alias):
            noms.add(noeud.name.rsplit('.', 1)[-1])
    return noms


class SymbolesMortsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cites = {}
        for chemin in BACKEND.rglob('*.py'):
            if _est_un_test(chemin) or 'migrations' in chemin.parts:
                continue
            if chemin.name == '__init__.py' and chemin.parent == SERVICES:
                continue  # la façade paresseuse ne compte pas
            cls.cites[chemin] = _noms_cites(chemin)

    def test_aucun_symbole_de_production_ou_de_pvgis_serie_sans_appelant(self):
        orphelins = []
        for module in MODULES:
            for nom in _symboles_publics(module):
                if nom in EN_ATTENTE:
                    continue
                if not any(nom in noms for chemin, noms in self.cites.items()
                           if chemin != module):
                    orphelins.append('%s::%s' % (module.name, nom))
        self.assertEqual(orphelins, [])
        for nom in ('production_du_layout', 'PanSansOrientation',
                    'serie_horaire'):
            for module in MODULES:
                self.assertNotIn(nom, _symboles_publics(module), module.name)
        fonctions = {noeud.name for noeud in _arbre(SERVICES / 'pertes.py').body
                     if isinstance(noeud, ast.FunctionDef)}
        self.assertNotIn('politique_du_calepinage', fonctions)

    def test_motif_non_simulable_ne_parle_plus_de_pertes_passees_a_pvgis(self):
        from apps.calepinage.views.simulation import publication_des_pertes

        class SansPoste:
            pk = 1
            pertes = []

        motif = publication_des_pertes(SansPoste())['motif_non_simulable']
        self.assertTrue(motif.strip())
        self.assertNotIn('PVGIS', motif)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
