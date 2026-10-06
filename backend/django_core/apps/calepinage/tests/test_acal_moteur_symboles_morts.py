# -*- coding: utf-8 -*-
"""ACAL327 — aucun symbole PUBLIC du moteur n'est sans appelant.

Constats C-ACAL-141 / C-ACAL-145. Le cache moteur AO (``cle_cache``,
``resultat_en_cache``, ``mettre_en_cache``, ``DUREE_CACHE_S``), les
exceptions ``VariantePerimee`` / ``SansVarianteRetenue`` et les convertisseurs
``parametres_vers_document`` / ``suggestions_vers_json`` étaient publiés sans
aucun appelant : la vraie clé de cache est ``tasks.cle_resultat``
(``calepinage:resultat:…``). Ils sont supprimés.

La garde, par AST : chaque nom de ``moteur_service.__all__`` et de
``moteur_io.__all__`` est LU (``from …moteur_io import X`` ou
``moteur_io.X``) par au moins un autre fichier Python du backend (``apps/``,
``core/`` — ``backend/parked`` n'en fait pas partie).

Run :
    python manage.py test apps.calepinage.tests.test_acal_moteur_symboles_morts
"""
from __future__ import annotations

import ast
import pathlib

from django.test import SimpleTestCase

from apps.calepinage import moteur_io, moteur_service

RACINE = pathlib.Path(__file__).resolve().parents[3]  # backend/django_core
MODULES = {
    'moteur_service': (moteur_service,
                       RACINE / 'apps' / 'calepinage' / 'moteur_service.py'),
    'moteur_io': (moteur_io, RACINE / 'apps' / 'calepinage' / 'moteur_io.py'),
}


def _references(chemin):
    """``{module: {noms}}`` — ce qu'un fichier lit de ``moteur_service`` /
    ``moteur_io`` : ``from …moteur_io import X`` ou ``moteur_io.X``.

    Qualifié par le MODULE (jamais un nom nu) : ``cle_cache`` existe aussi
    dans ``ventes.taille_detail`` et ``core.bi_cache`` — un homonyme n'est
    pas un appelant.
    """
    texte = chemin.read_text(encoding='utf-8', errors='replace')
    if 'moteur_service' not in texte and 'moteur_io' not in texte:
        return {}
    try:
        arbre = ast.parse(texte)
    except SyntaxError:
        return {}
    lus = {nom: set() for nom in MODULES}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            source = (noeud.module or '').rsplit('.', 1)[-1]
            if source in lus:
                lus[source].update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.Attribute) and isinstance(
                noeud.value, ast.Name) and noeud.value.id in lus:
            lus[noeud.value.id].add(noeud.attr)
    return lus


def _references_hors_module():
    """Les noms lus de chaque module par TOUT autre fichier du backend
    (``apps/``, ``core/`` ; ``backend/parked`` n'en fait pas partie)."""
    lus = {nom: set() for nom in MODULES}
    moi = pathlib.Path(__file__).resolve()
    for dossier in (RACINE / 'apps', RACINE / 'core'):
        for chemin in dossier.rglob('*.py'):
            if chemin.resolve() == moi:
                continue
            for nom_module, noms in _references(chemin).items():
                if chemin.resolve() != MODULES[nom_module][1].resolve():
                    lus[nom_module] |= noms
    return lus


class SymbolesMortsTest(SimpleTestCase):

    def test_aucun_symbole_public_du_moteur_n_est_sans_appelant(self):
        references = _references_hors_module()
        orphelins = []
        for nom_module, (module, _chemin) in MODULES.items():
            for nom in module.__all__:
                if nom not in references[nom_module]:
                    orphelins.append('%s.%s' % (nom_module, nom))
        self.assertEqual(orphelins, [],
                         'symboles publics du moteur sans appelant')

    def test_les_symboles_supprimes_ont_disparu(self):
        for nom in ('cle_cache', 'resultat_en_cache', 'mettre_en_cache',
                    'DUREE_CACHE_S', 'VariantePerimee',
                    'SansVarianteRetenue'):
            self.assertFalse(hasattr(moteur_service, nom), nom)
        for nom in ('parametres_vers_document', 'suggestions_vers_json'):
            self.assertFalse(hasattr(moteur_io, nom), nom)

    def test_la_cle_de_cache_survivante_est_celle_de_tasks(self):
        from apps.calepinage import tasks

        self.assertTrue(callable(tasks.cle_resultat))
        self.assertTrue(hasattr(tasks, 'DUREE_CACHE_S'))
