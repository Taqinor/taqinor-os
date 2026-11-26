"""ACAL702 — ``cascade.plages`` : chaque perte face à sa bande PUBLIÉE.

Les bandes viennent de ``data/plages_usuelles.json`` (ACAL701 : une page
publiée relue, son url, sa date). Une étape appliquée qui a une bande est
« dans_la_plage » (min ≤ perte_pct ≤ max) ou « inhabituel » ; une étape
omise, un gain ou une étape sans bande est ABSENTE — jamais « dans la plage »
par défaut. Aucun seuil en code ; la valeur publiée n'est ni bornée ni
corrigée, et rien n'arrête la simulation.
"""
from __future__ import annotations

import functools
import json
import pathlib

from .valeurs import nombre as _nombre

#: Chemin du fichier de bandes publiées (ACAL701) ; ``parents[1]`` = le
#: dossier de l'app calepinage, qui porte ``data/`` — aucune valeur chiffrée.
FICHIER = pathlib.Path(__file__).resolve().parents[1] / 'data' / 'plages_usuelles.json'
MOTIF_AUCUNE_BANDE = 'aucune bande sourcée'

__all__ = ['FICHIER', 'MOTIF_AUCUNE_BANDE', 'charger', 'evaluer']


@functools.lru_cache(maxsize=1)
def charger():
    """Le fichier de bandes, lu une fois ; absent ou illisible ⇒ ``{}``."""
    try:
        return json.loads(FICHIER.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _pastille(valeur, bande):
    bas, haut = _nombre(bande.get('min')), _nombre(bande.get('max'))
    if valeur is None or bas is None or haut is None:
        return None
    statut = 'dans_la_plage' if bas <= valeur <= haut else 'inhabituel'
    return {'statut': statut, 'min': bas, 'max': haut,
            'unite': bande.get('unite'), 'url': bande.get('url'),
            'date_lecture': bande.get('date_lecture'),
            'citation': bande.get('citation')}  # ACAL1625 — la phrase de la page


def _citee(bande):
    """ACAL1625 — une bande n'est lue que si elle porte son url ET la phrase
    citée de la page : jamais un chiffre sans sa page."""
    return (isinstance(bande, dict) and str(bande.get('url') or '').startswith('https://')
            and bool(str(bande.get('citation') or '').strip()))


def evaluer(cascade, donnees=None):
    """``{etapes: {<etape>: pastille}, total, motif_absence}``."""
    donnees = charger() if donnees is None else (donnees or {})
    bandes = {bande.get('etape'): bande
              for bande in donnees.get('bandes') or ()
              if _citee(bande)}
    etapes = {}
    for etape in (cascade or {}).get('etapes') or ():
        bande = bandes.get(etape.get('etape'))
        if bande is None or etape.get('motif_omission') or etape.get('gain'):
            continue
        pastille = _pastille(_nombre(etape.get('perte_pct')), bande)
        if pastille is not None:
            etapes[etape['etape']] = pastille
    total = donnees.get('total')
    total = (_pastille(_nombre((cascade or {}).get('total_pct')), total)
             if _citee(total) else None)
    return {'etapes': etapes, 'total': total,
            'motif_absence': '' if bandes else MOTIF_AUCUNE_BANDE}
