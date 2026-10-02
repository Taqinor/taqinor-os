# -*- coding: utf-8 -*-
"""QJR667 — toute ``@action`` de ``DevisViewSet`` a un appelant ÉCRAN.

Une action sans appelant est une fonctionnalité morte côté utilisateur : le
backend la maintient, aucun écran ne la déclenche. La garde lit l'AST de
``views/devis.py`` (chaque ``@action`` du ``DevisViewSet`` et son
``url_path``), puis cherche ce chemin dans les clients d'API du frontend
(``frontend/src``, dont ``api/*.js`` et les pages qui appellent l'API en
direct) et dans le site (``apps/web/src``).

Une action volontairement sans écran (appelée par un tiers, par un script, ou
en attente de son écran) porte, dans les lignes qui précèdent sa fonction (le
décorateur inclus), un marqueur ``# api-only: <raison>`` — la raison est
OBLIGATOIRE, un marqueur nu échoue.
"""
import ast
import os
import re

from django.test import SimpleTestCase

RACINE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', '..'))
VUE_DEVIS = os.path.join(RACINE, 'backend', 'django_core', 'apps', 'ventes',
                         'views', 'devis.py')
EXTENSIONS = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.astro')
MARQUEUR = re.compile(r'#\s*api-only\s*:\s*(\S.*)$')


def _actions_devis():
    """[(nom, url_path, ligne_decorateur_haut, ligne_def)] du DevisViewSet."""
    with open(VUE_DEVIS, encoding='utf-8') as f:
        source = f.read()
    arbre = ast.parse(source)
    classe = next(n for n in arbre.body
                  if isinstance(n, ast.ClassDef) and n.name == 'DevisViewSet')
    sortie = []
    for fn in classe.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        for deco in fn.decorator_list:
            if not (isinstance(deco, ast.Call)
                    and getattr(deco.func, 'id', None) == 'action'):
                continue
            url_path = fn.name.replace('_', '-')
            for kw in deco.keywords:
                if kw.arg == 'url_path':
                    url_path = ast.literal_eval(kw.value)
            haut = min(d.lineno for d in fn.decorator_list)
            sortie.append((fn.name, url_path, haut, fn.lineno))
    return sortie, source.splitlines()


def _textes_ecrans():
    """Le texte de tout le code écran (frontend/src dont api/*.js, + web)."""
    dossiers = [os.path.join(RACINE, 'frontend', 'src'),
                os.path.join(RACINE, 'apps', 'web', 'src')]
    textes = []
    for dossier in dossiers:
        for courant, _sous, fichiers in os.walk(dossier):
            for nom in fichiers:
                if not nom.endswith(EXTENSIONS) or '.test.' in nom:
                    continue
                chemin = os.path.join(courant, nom)
                with open(chemin, encoding='utf-8', errors='ignore') as f:
                    textes.append(f.read())
    return '\n'.join(textes)


def _motif_appelant(url_path):
    """``devis/[${id}/]<url_path>`` suivi de ``/``, d'un guillemet, d'un ``?``
    ou de la fin — ancré sur ``devis/`` pour que ``dupliquer`` ou ``historique``
    ne s'accrochent pas à un autre module (stock, calepinage…)."""
    base = re.split(r'/\(', url_path)[0]
    return re.compile(r'devis/(?:\$\{[^}]+\}/)?' + re.escape(base)
                      + r"""(?:/|['"`?]|\Z)""")


class ChaqueActionDevisAUnAppelantEcran(SimpleTestCase):
    def test_garde_connait_les_actions(self):
        actions, _lignes = _actions_devis()
        self.assertGreater(len(actions), 40)
        self.assertIn('generer-pdf', [u for _n, u, _h, _d in actions])

    def test_chaque_action_a_un_appelant_ecran_ou_un_marqueur_api_only(self):
        actions, lignes = _actions_devis()
        ecrans = _textes_ecrans()
        orphelines = []
        for nom, url_path, haut, def_ligne in actions:
            if _motif_appelant(url_path).search(ecrans):
                continue
            bloc = lignes[max(0, haut - 4):def_ligne]
            if any(MARQUEUR.search(ligne) for ligne in bloc):
                continue
            orphelines.append('%s (url_path=%r, views/devis.py:%d)'
                              % (nom, url_path, def_ligne))
        self.assertEqual(
            orphelines, [],
            "Action(s) DevisViewSet sans appelant écran : ajouter l'appel "
            "dans frontend/src, ou un marqueur "
            "« # api-only: <raison> » au-dessus du décorateur.")

    def test_un_marqueur_api_only_porte_toujours_une_raison(self):
        with open(VUE_DEVIS, encoding='utf-8') as f:
            nus = [i + 1 for i, ligne in enumerate(f)
                   if re.search(r'#\s*api-only\b', ligne)
                   and not MARQUEUR.search(ligne)]
        self.assertEqual(nus, [], 'marqueur api-only sans raison, lignes %s'
                         % nus)
