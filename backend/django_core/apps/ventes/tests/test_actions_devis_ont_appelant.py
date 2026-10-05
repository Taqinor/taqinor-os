# -*- coding: utf-8 -*-
"""QJR667 — toute ``@action`` de ``DevisViewSet`` a un appelant ÉCRAN.

Une action sans appelant est une fonctionnalité morte côté utilisateur : le
backend la maintient, aucun écran ne la déclenche. La garde découvre les
actions par ``DevisViewSet.get_extra_actions()`` (SPL130 : indépendant du
fichier qui les définit — ``views/devis*.py``, ``views/economie.py``), lit leur
source par ``inspect``, puis cherche leur ``url_path`` dans les clients d'API
du frontend
(``frontend/src``, dont ``api/*.js`` et les pages qui appellent l'API en
direct) et dans le site (``apps/web/src``).

Une action volontairement sans écran (appelée par un tiers, par un script, ou
en attente de son écran) porte, dans les lignes qui précèdent sa fonction (le
décorateur inclus), un marqueur ``# api-only: <raison>`` — la raison est
OBLIGATOIRE, un marqueur nu échoue.
"""
import inspect
import os
import re
from pathlib import Path

from django.test import SimpleTestCase

RACINE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', '..'))
VUES = Path(RACINE) / 'backend' / 'django_core' / 'apps' / 'ventes' / 'views'
EXTENSIONS = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.astro')
MARQUEUR = re.compile(r'#\s*api-only\s*:\s*(\S.*)$')
#: 54 ``@action`` de ``views/devis.py`` (dont ``facturer-complet``, 05/10) +
#: ``economie`` (views/economie.py) + ``economie_pompage``
#: (views/economie_pompage.py, AGR206).
NB_ACTIONS = 56


def _vues_devis():
    """``views/devis.py`` et ses modules de découpe ``views/devis_*.py``."""
    return [VUES / 'devis.py'] + sorted(VUES.glob('devis_*.py'))


def _actions_devis():
    """[(nom, url_path, ligne_decorateur_haut, ligne_def, lignes, fichier)]
    de chaque route de ``DevisViewSet.get_extra_actions()``."""
    from apps.ventes.views.devis import DevisViewSet
    sortie = []
    for fn in DevisViewSet.get_extra_actions():
        brut = inspect.unwrap(fn)
        chemin = inspect.getsourcefile(brut)
        bloc, haut = inspect.getsourcelines(brut)
        decalage = next(i for i, ligne in enumerate(bloc)
                        if re.match(r'\s*(async\s+)?def\s', ligne))
        with open(chemin, encoding='utf-8') as f:
            lignes = f.read().splitlines()
        sortie.append((fn.__name__, fn.url_path, haut, haut + decalage,
                       lignes, os.path.basename(chemin)))
    return sortie


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
        actions = _actions_devis()
        self.assertEqual(len(actions), NB_ACTIONS)
        self.assertIn('generer-pdf', [a[1] for a in actions])

    def test_chaque_action_a_un_appelant_ecran_ou_un_marqueur_api_only(self):
        actions = _actions_devis()
        ecrans = _textes_ecrans()
        orphelines = []
        for nom, url_path, haut, def_ligne, lignes, fichier in actions:
            if _motif_appelant(url_path).search(ecrans):
                continue
            bloc = lignes[max(0, haut - 4):def_ligne]
            if any(MARQUEUR.search(ligne) for ligne in bloc):
                continue
            orphelines.append('%s (url_path=%r, views/%s:%d)'
                              % (nom, url_path, fichier, def_ligne))
        self.assertEqual(
            orphelines, [],
            "Action(s) DevisViewSet sans appelant écran : ajouter l'appel "
            "dans frontend/src, ou un marqueur "
            "« # api-only: <raison> » au-dessus du décorateur.")

    def test_un_marqueur_api_only_porte_toujours_une_raison(self):
        nus = []
        for chemin in _vues_devis():
            with open(chemin, encoding='utf-8') as f:
                nus += ['%s:%d' % (chemin.name, i + 1)
                        for i, ligne in enumerate(f)
                        if re.search(r'#\s*api-only', ligne)
                        and not MARQUEUR.search(ligne)]
        self.assertEqual(nus, [], 'marqueur api-only sans raison, lignes %s'
                         % nus)

    def test_les_marqueurs_api_only_sont_tous_lus(self):
        """Non-vacuité : les deux marqueurs (``dupliquer``, ``renouveler``)
        sont trouvés, où que leurs actions vivent."""
        marques = [ligne for chemin in _vues_devis()
                   for ligne in chemin.read_text(encoding='utf-8')
                   .splitlines() if MARQUEUR.search(ligne)]
        self.assertGreaterEqual(len(marques), 2)
