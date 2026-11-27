"""Revue ACAL1655 — AUCUN motif d'omission de la cascade ne crie.

Le test importe les modules des étapes et de la chaîne, et passe en revue
TOUTES les constantes dont le nom contient ``MOTIF`` ainsi que les tables
``EXCLUSIVITES`` et ``TOUJOURS_OMISES`` : aucune majuscule d'insistance
(mot de 4 lettres majuscules ou plus hors sigles), aucun jargon de code.
"""
from __future__ import annotations

import importlib
import pkgutil
import re
import unittest

from apps.calepinage.services import chaine_pertes, etapes

ACRONYMES = {'STC', 'MPPT', 'PVGIS', 'LID', 'IAM', 'NOCT', 'TRI', 'DEM'}
INTERDITS = ('en v1', 'PV*SOL', 'littéral', "n'est pas dérate",
             'silence est explicite', 'fiche de le ', 'TOUJOURS_OMISES')
TABLES = ('EXCLUSIVITES', 'TOUJOURS_OMISES')
AUTRES = ('CLES_METHODE',)


def _textes(valeur):
    if isinstance(valeur, str):
        yield valeur
    elif isinstance(valeur, dict):
        for v in valeur.values():
            yield from _textes(v)
    elif isinstance(valeur, (tuple, list, set, frozenset)):
        for v in valeur:
            yield from _textes(v)


def _modules():
    yield chaine_pertes
    yield etapes
    for info in pkgutil.iter_modules(etapes.__path__):
        yield importlib.import_module('%s.%s' % (etapes.__name__, info.name))


def _tous_les_motifs():
    for module in _modules():
        for nom, valeur in vars(module).items():
            if 'MOTIF' in nom.upper() or nom in TABLES or nom in AUTRES:
                for texte in _textes(valeur):
                    yield '%s.%s' % (module.__name__.rsplit('.', 1)[-1], nom), texte


class MotifsSansCrisTest(unittest.TestCase):
    def test_le_balayage_voit_beaucoup_de_motifs(self):
        self.assertGreater(len(list(_tous_les_motifs())), 80)

    def test_aucun_motif_ne_crie_ni_ne_parle_code(self):
        fautes = []
        for nom, texte in _tous_les_motifs():
            criees = [m for m in re.findall(r'\b[A-ZÀ-Ý]{4,}\b', texte)
                      if m not in ACRONYMES]
            if criees:
                fautes.append((nom, criees))
            fautes.extend((nom, i) for i in INTERDITS + ('DÉJÀ',) if i in texte)
            fautes.extend((nom, c) for c in re.findall(r'CALX\d*', texte))
        self.assertEqual(fautes, [])
