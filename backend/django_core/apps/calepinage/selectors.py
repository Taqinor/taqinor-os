"""Sélecteurs (lectures) du module Calepinage.

FRONTIÈRE INTER-APPS (import-linter) — une AUTRE app qui a besoin de LIRE des
données de ce module passe par une fonction de CE fichier, jamais en important
``apps.calepinage.models`` / ``.views``. Symétriquement, les lectures dont ce
module a besoin chez crm / ventes / ao passent par LEURS ``selectors.py``.

Toutes les fonctions sont en LECTURE PURE et BORNÉES SOCIÉTÉ : la société est
toujours celle passée en argument, jamais lue d'un corps de requête.
"""
from __future__ import annotations

#: CAL45 — les sections de réglages, dans l'ordre du contrat publié
#: (``contract_samples/parametres_calepinage.json``). Source unique de la FORME
#: rendue : l'endpoint, l'écran et les tests lisent la même liste.
SECTIONS_PARAMETRES = (
    'imagerie',
    'degagements',
    'zones_types',
    'gabarits_disposition',
    'presets',
    'favoris_materiel',
    'gabarits_dossier',
)


def parametres_de_societe(company):
    """CAL45 — les réglages calepinage de ``company``, TOUJOURS complets.

    ÉQUIVALENCE GARANTIE : une société qui n'a JAMAIS réglé quoi que ce soit
    reçoit les sept sections à ``{}`` — c'est-à-dire « comportement
    d'aujourd'hui, strictement inchangé ». Les clés sont toutes présentes dans
    les deux cas : un appelant n'a jamais à deviner si une section manque
    parce qu'elle est vide ou parce que le serveur l'a omise.

    Lecture PURE : aucun enregistrement n'est créé ici (un GET qui écrit en
    base est un GET qui ment).
    """
    from .models import ParametresCalepinage

    vide = {section: {} for section in SECTIONS_PARAMETRES}
    if company is None:
        return vide
    reglages = (ParametresCalepinage.objects
                .filter(company=company)
                .order_by('id')
                .first())
    if reglages is None:
        return vide
    return {
        section: (getattr(reglages, section, None) or {})
        for section in SECTIONS_PARAMETRES
    }
