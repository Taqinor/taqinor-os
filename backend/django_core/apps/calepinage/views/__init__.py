"""Vues (HTTP) du module « calepinage » — CAL233.

Même raison que pour ``services/`` : un module ``views.py`` et un paquet
``views/`` ne peuvent pas coexister, et le module Calepinage a plusieurs
familles de vues (pivot, moteur, réglages, sorties, import/export de layout).
Le paquet est donc posé UNE fois, avant toute lane.

LA RÈGLE
--------
* un SOUS-MODULE par famille (``calepinages``, ``moteur``, ``parametres``,
  ``sorties``, ``io_layout``…) ;
* ce ``__init__`` RÉ-EXPORTE les classes publiques ;
* ``urls.py`` enregistre TOUT sous DEUX formes d'URL, et seulement deux :
  ``/api/django/calepinage/calepinages/<pk>/…`` (sous-ressources en ``@action``
  du routeur DRF) et ``/api/django/calepinage/parametres/``. Deux familles
  d'URL pour un même objet, c'est l'incident PACT10 par construction ;
  ``tests/test_structure_urls.py`` échoue si une URL sort de ces deux formes.

Tout viewset scopé société hérite de ``core.viewsets.CompanyScopedModelViewSet``
(ARC2 : queryset filtré sur ``request.user.company``, ``company`` forcée côté
serveur, jamais lue du corps de requête).
"""
from __future__ import annotations

#: Les sous-modules de vues (documentaire — aucun import au chargement).
SOUS_MODULES = (
    'calepinages',    # le pivot + ses @action (sous-ressources)
    'parametres',     # réglages société (CAL45)
    'moteur',         # appels au moteur pur core.calepinage
    'photos',         # CAL52 — photos de site (sous-ressource du pivot)
    'sorties',        # PDF / SVG
    'io_layout',      # import/export du document roof_layout
)

#: Les seuls préfixes d'URL admis sous ``/api/django/calepinage/``.
#:
#: CAL22 — ``moteur`` REJOINT les deux premiers, et c'est une exception
#: BORNÉE, pas un relâchement : la règle « une seule forme d'URL » protège
#: l'OBJET MÉTIER (un calepinage se sert sous ``calepinages/<pk>/…``, ses
#: sous-ressources en ``@action``, jamais sous une seconde famille). Le moteur
#: n'est pas cet objet : c'est un CALCUL SANS ÉTAT, sans identifiant, qui
#: n'appartient à aucun calepinage — et son chemin
#: (``/api/django/calepinage/moteur/calculer/``) est figé depuis le jour 1 par
#: le contrat committé ``contract_samples/moteur_calculer.json`` (PACT10), que
#: la lane d'en face consomme déjà. Le servir ailleurs aurait donc cassé le
#: contrat pour sauver la lettre d'une règle qui ne le visait pas.
PREFIXES_URL_AUTORISES = ('calepinages', 'moteur', 'parametres')

__all__ = ['SOUS_MODULES', 'PREFIXES_URL_AUTORISES']


def __getattr__(nom):
    """Ré-export PARESSEUX des classes publiques des sous-modules de vues."""
    from importlib import import_module

    for sous_module in SOUS_MODULES:
        chemin = f'{__name__}.{sous_module}'
        try:
            module = import_module(chemin)
        except ModuleNotFoundError as erreur:
            if erreur.name != chemin:
                raise
            continue
        if hasattr(module, nom):
            return getattr(module, nom)
    raise AttributeError(
        f"Le paquet de vues « calepinage » n'expose pas « {nom} ». "
        f"Sous-modules connus : {', '.join(SOUS_MODULES)}.")
