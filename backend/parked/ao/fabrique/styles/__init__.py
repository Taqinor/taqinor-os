"""AOF117 — chargement de la feuille de style PROPRE de la fabrique AO.

La feuille est INLINÉE dans le document rendu (`<style>…</style>`) plutôt que
liée : `core.pdf.render_pdf` reçoit un HTML autonome, sans `base_url`, sans
fichier à résoudre et sans réseau. Un pli déposé ne doit dépendre d'aucune
ressource externe au moment du rendu.

Aucun jeton n'est emprunté à `apps/ventes/quote_engine` (règle #4).
"""
from __future__ import annotations

import pathlib

DOSSIER = pathlib.Path(__file__).resolve().parent

#: Les feuilles disponibles. Une pièce ne choisit pas sa charte : elle prend
#: `base`, éventuellement complétée par une feuille de composant.
FEUILLES = ('base',)


class FeuilleInconnue(KeyError):
    """Une pièce demande une feuille qui n'existe pas."""


def chemin(nom='base'):
    if nom not in FEUILLES:
        raise FeuilleInconnue(
            'feuille de style inconnue : %r (disponibles : %s)'
            % (nom, ', '.join(FEUILLES)))
    return DOSSIER / ('%s.css' % nom)


def css(nom='base'):
    """Le texte de la feuille — lu une fois, mis en cache par le module."""
    if nom not in _CACHE:
        _CACHE[nom] = chemin(nom).read_text(encoding='utf-8')
    return _CACHE[nom]


_CACHE = {}


def contexte_style(nom='base'):
    """Le fragment de contexte de gabarit portant la feuille inlinée."""
    return {'css_fabrique': css(nom)}
