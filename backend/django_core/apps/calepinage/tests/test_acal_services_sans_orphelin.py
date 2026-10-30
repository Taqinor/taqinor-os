# -*- coding: utf-8 -*-
"""ACAL293 — aucun module ni enveloppe de service sans consommateur.

Ce qui est prouvé ici (AST, sans base) :

* les quatre symboles morts n'existent plus : ``services/commentaires.py``
  (jumeau du chatter ``records``), ``bifacial.poste_bifacial``,
  ``thermique.poste_thermique`` et ``pvgis_serie.vider_le_cache`` ;
* chaque module de ``apps/calepinage/services/`` est IMPORTÉ par au moins un
  fichier non-test du backend (la façade ``services/__init__.py`` ne compte
  pas) — sauf les modules dont le sort est décidé ailleurs, NOMMÉS ci-dessous.

Run :
    python manage.py test apps.calepinage.tests.test_acal_services_sans_orphelin
"""
from __future__ import annotations

import ast
import pathlib
import unittest

BACKEND = pathlib.Path(__file__).resolve().parents[3]
SERVICES = BACKEND / 'apps' / 'calepinage' / 'services'
RACINES = (BACKEND / 'apps', BACKEND / 'core')

#: Modules sans importeur dont le sort est décidé PAR UNE AUTRE tâche.
DECIDES_AILLEURS = {
    'kits': '_construire_kit_de_pose — sort décidé avec C-ACAL-033 (D-ACAL-17)',
    'traduction': 'gardé (D-ACAL-17)',
}


def _definitions(chemin):
    arbre = ast.parse(chemin.read_text(encoding='utf-8'))
    noms = set()
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.ClassDef)):
            noms.add(noeud.name)
    return noms


def _est_un_test(chemin):
    morceaux = chemin.parts
    return ('tests' in morceaux or chemin.name.startswith('test')
            or chemin.name.startswith('tests_'))


def _importe(arbre, nom):
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            module = noeud.module or ''
            if module == nom or module.endswith('.' + nom):
                return True
            if any(alias.name == nom for alias in noeud.names):
                return True
        elif isinstance(noeud, ast.Import):
            if any(alias.name.endswith('.' + nom) for alias in noeud.names):
                return True
    return False


class ServicesSansOrphelinTest(unittest.TestCase):

    def test_ces_quatre_symboles_n_existent_plus(self):
        self.assertFalse((SERVICES / 'commentaires.py').exists())
        for module, nom in (('bifacial.py', 'poste_bifacial'),
                            ('thermique.py', 'poste_thermique'),
                            ('pvgis_serie.py', 'vider_le_cache')):
            self.assertNotIn(nom, _definitions(SERVICES / module), module)

    def test_aucun_module_de_services_sans_importeur_hors_tests(self):
        modules = sorted(chemin.stem for chemin in SERVICES.glob('*.py')
                         if chemin.name != '__init__.py')
        candidats = {}
        for racine in RACINES:
            for chemin in racine.rglob('*.py'):
                if (_est_un_test(chemin) or 'migrations' in chemin.parts
                        or chemin == SERVICES / '__init__.py'):
                    continue
                try:
                    texte = chemin.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    continue
                candidats[chemin] = texte
        orphelins = []
        for nom in modules:
            if nom in DECIDES_AILLEURS:
                continue
            propre = SERVICES / (nom + '.py')
            importe = False
            for chemin, texte in candidats.items():
                if chemin == propre or nom not in texte:
                    continue
                try:
                    arbre = ast.parse(texte)
                except SyntaxError:
                    continue
                if _importe(arbre, nom):
                    importe = True
                    break
            if not importe:
                orphelins.append(nom)
        self.assertEqual(orphelins, [])


# --- ACAL347 : le passif ``services_appeles`` du module est drainé ----------
RACINE = BACKEND.parents[1]
BASE_SERVICES = RACINE / 'scripts' / 'services_appeles_allow.txt'
#: Plafond nommé (ACAL347 d) : fonctions réelles sans écran encore ouvertes.
BASE_MAX = 5
#: Jumeaux prouvés sans valeur, supprimés (ACAL347 c) : module -> symboles.
JUMEAUX_SUPPRIMES = {
    'presets.py': ('enregistrer_jeu', 'retirer_jeu'),
    'batterie.py': ('tranches_horaires',),
    'commentaires.py': ('commentaires_du_calepinage', 'deposer_commentaire'),
}


class ServicesAppelesDraineTest(unittest.TestCase):

    def test_aucune_fonction_publique_de_service_sans_appelant_hors_module(
            self):
        import subprocess
        import sys
        lignes = [ligne.strip() for ligne in
                  BASE_SERVICES.read_text(encoding='utf-8').splitlines()
                  if ligne.strip() and not ligne.lstrip().startswith('#')
                  and 'apps/calepinage/' in ligne]
        self.assertLessEqual(len(lignes), BASE_MAX, lignes)
        resultat = subprocess.run(
            [sys.executable,
             str(RACINE / 'scripts' / 'check_services_appeles.py'),
             '--app', 'calepinage'],
            capture_output=True, text=True, cwd=str(RACINE))
        self.assertEqual(resultat.returncode, 0,
                         resultat.stdout + resultat.stderr)

    def test_les_jumeaux_supprimes_ne_reviennent_pas(self):
        for module, symboles in JUMEAUX_SUPPRIMES.items():
            chemin = SERVICES / module
            if not chemin.exists():
                continue
            presents = _definitions(chemin)
            for nom in symboles:
                with self.subTest(module=module, nom=nom):
                    self.assertNotIn(nom, presents)
