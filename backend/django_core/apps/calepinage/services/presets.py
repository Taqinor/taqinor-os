"""CAL197 — presets de conception PROPRES au module (section ``presets`` de
``ParametresCalepinage``, CAL45 — aucun nouveau modèle).

UNE SEULE SOURCE, JAMAIS UNE COPIE VENUE D'AILLEURS
----------------------------------------------------
Ce module LIT les presets PROPRES à l'atelier dans la section ``presets`` des
réglages société (``selectors.presets_de_societe``) et valide cette section à
l'écriture (``normaliser_section_presets``). L'ÉCRITURE a un seul chemin :
``PUT parametres/`` → ``enregistrer_parametres`` (l'écran Bibliothèque renvoie
la section entière, jeux et kits compris) ; les jumeaux ``enregistrer_jeu`` /
``retirer_jeu``, sans appelant de production, ont été retirés (ENF18).

SOLMVP15 — il y avait une SECONDE source, lue côte à côte : les presets de
portee société du module d'appels d'offres, jamais copiés dans la section du
module. Ce module-là sort du produit, sa table part avec lui : il n'en reste
qu'une source. Les jeux maison sont intacts — rien n'a été perdu ni copié.

Aucune valeur codée en dur : ce service ne pose AUCUN défaut, il lit ce qui
est rangé et refuse ce qui est invalide, en NOMMANT le champ fautif.
"""
from __future__ import annotations

from .approbation import CLE_EXIGEE

#: Clé, DANS la section ``presets``, qui porte la liste des jeux MAISON.
CLE_JEUX = 'jeux'

#: La section des réglages société que ce module porte (CAL45).
SECTION = 'presets'

__all__ = [
    'CLE_JEUX', 'SECTION', 'CLE_APPROBATION_EXIGEE',
    'jeux_de_societe', 'normaliser_section_presets',
]

#: CALX348 — la clé, DANS la section ``presets``, qui exige l'approbation
#: (CALX347) avant de retenir une variante. Source UNIQUE :
#: ``services/approbation.py::CLE_EXIGEE`` (qui la LIT) ; ce module-ci la
#: VALIDE à l'écriture (``normaliser_section_presets``). Off par défaut : une
#: société qui n'a jamais réglé cette option retrouve le comportement
#: d'aujourd'hui.
CLE_APPROBATION_EXIGEE = CLE_EXIGEE


def jeux_de_societe(company):
    """Les presets PROPRES au module (section ``presets.jeux``), lecture pure.

    ÉQUIVALENCE GARANTIE : une société qui n'a jamais rien réglé reçoit une
    liste VIDE — comportement d'aujourd'hui, strictement inchangé.
    """
    from ..selectors import parametres_de_societe

    presets = parametres_de_societe(company).get('presets') or {}
    jeux = presets.get(CLE_JEUX)
    return jeux if isinstance(jeux, list) else []


def normaliser_section_presets(valeur):
    """CALX348 — la section ``presets`` VALIDÉE, sans rien retrancher.

    La section range des jeux maison, le catalogue de kits, l'interrupteur
    du feu vert (CAL206)… : ce normaliseur n'en touche AUCUNE clé. Il ne
    valide que ``approbation_exigee`` : un BOOLÉEN, ou rien. Une valeur d'une
    autre nature (« oui », 1, une liste) est REFUSÉE en nommant le champ —
    jamais interprétée : un « oui » accepté en silence laisserait croire à
    la société que l'approbation est exigée alors que la lecture stricte
    (``approbation.approbation_exigee``, ``is True``) la tient pour éteinte.

    ACAL287 — ``versions_conservees`` (borne de purge des versions,
    ``services.versions``) : un entier STRICTEMENT positif, ou ``null``
    (purge éteinte). Toute autre valeur (0, -1, « 2 », 2.5, un booléen) est
    REFUSÉE en nommant ``presets.versions_conservees`` — jamais lue « OFF »
    en silence alors que la société croit avoir borné l'historique.

    Raises:
        ReglageInvalide: ``approbation_exigee`` n'est pas un booléen, ou
            ``versions_conservees`` n'est ni un entier > 0 ni ``null``.
    """
    from .parametres import ReglageInvalide
    from .versions import CLE_BORNE_PURGE

    if isinstance(valeur, dict) and CLE_BORNE_PURGE in valeur:
        borne = valeur[CLE_BORNE_PURGE]
        if borne is not None and (isinstance(borne, bool)
                                  or not isinstance(borne, int)
                                  or borne <= 0):
            raise ReglageInvalide(
                'Le nombre de versions conservées est un entier strictement '
                f'positif, ou vide pour tout garder (reçu : {borne!r}).',
                champ=CLE_BORNE_PURGE, section=SECTION)
    if not isinstance(valeur, dict) or CLE_APPROBATION_EXIGEE not in valeur:
        return valeur
    exigee = valeur[CLE_APPROBATION_EXIGEE]
    if exigee is None or isinstance(exigee, bool):
        return valeur
    raise ReglageInvalide(
        "« Approbation exigée » se règle par oui ou non (booléen) "
        f"(reçu : {type(exigee).__name__}).",
        champ=CLE_APPROBATION_EXIGEE)
