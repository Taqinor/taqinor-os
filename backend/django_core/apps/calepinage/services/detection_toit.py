"""ACAL485 (D-ACAL-33) — détection du toit par IA : une PROPOSITION à confirmer.

Passe par la capacité ``vision_toit`` du noyau (``core.ai.registry.get_provider``,
ACAL489) — jamais un appel direct au fournisseur. Seuls les octets et le type de
l'image partent (ni nom, ni adresse, ni lead, ni emprise) ; l'emprise ne sert
qu'ICI, à convertir les fractions d'image rendues en longitude/latitude. Rien
n'est écrit sur le calepinage, l'image n'est jamais stockée ; la trace d'usage
est le journal IA du noyau (``usage_context``). Forme servie :
``contract_samples/calepinage_detection_toit.json`` (ACAL391).
"""
from __future__ import annotations

import functools
import json
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

FEATURE = 'calepinage.detection_toit'
MOTIF_NON_CONFIGUREE = "La détection du toit n'est pas configurée sur ce serveur."
MOTIF_BUDGET = "Le budget IA du mois est épuisé : la détection du toit reprendra le mois prochain."
DETAIL_INDISPONIBLE = ("La détection du toit est indisponible pour le moment : "
                       "tracez le toit à la main.")
_COINS = ('ouest', 'sud', 'est', 'nord')
#: Toutes les origines connues ; ``origines_acceptees`` dit celles OUVERTES.
ORIGINES = ('importee', 'carte')
#: Bornes de chaque coin (degrés) : la FORME publiée au schéma.
BORNES_COINS = {'ouest': (-180, 180), 'est': (-180, 180),
                'sud': (-90, 90), 'nord': (-90, 90)}


_SCHEMA_LAYOUT = (Path(__file__).resolve().parent.parent / 'contract_samples'
                  / 'roof_layout_v2.schema.json')


class DetectionIndisponible(Exception):
    """Aucun fournisseur actif, ou fournisseur en erreur : 503, tracé manuel."""


def origines_acceptees():
    """``carte`` seulement si Reda l'a ouverte (conditions de l'imagerie lues)."""
    return list(ORIGINES) if getattr(settings, 'DETECTION_TOIT_CAPTURE_CARTE', False) else ['importee']


def _fournisseur(company_id):
    from core.ai.registry import get_provider
    from core.ai.usage import usage_context

    with usage_context(company_id=company_id, feature_key=FEATURE):
        try:
            fournisseur = get_provider('vision_toit')
        except ValueError:  # capacité absente du noyau : indisponible, jamais 500
            return None
    return None if getattr(fournisseur, 'key', 'noop') == 'noop' else fournisseur


def disponibilite(company_id):
    disponible = _fournisseur(company_id) is not None
    motif = ''
    if not disponible:
        from core.ai.usage import budget_status
        motif = MOTIF_BUDGET if budget_status(company_id).depasse else MOTIF_NON_CONFIGUREE
    return {'disponible': disponible, 'motif': motif, 'origines_acceptees': origines_acceptees()}


def coins_emprise(brut):
    """``{ouest, sud, est, nord}`` en degrés, chacun dans ses bornes, ou
    ``None`` si la FORME est illisible (texte non JSON, coin absent, non
    numérique, hors bornes) — ce que le schéma publié dit (400)."""
    if isinstance(brut, str):
        try:
            brut = json.loads(brut)
        except ValueError:
            return None
    if not isinstance(brut, dict):
        return None
    try:
        emprise = {coin: float(brut[coin]) for coin in _COINS}
    except (KeyError, TypeError, ValueError):
        return None
    if not all(bas <= emprise[coin] <= haut
               for coin, (bas, haut) in BORNES_COINS.items()):
        return None
    return emprise


def lire_emprise(brut):
    """``{ouest, sud, est, nord}`` en degrés, ou ``None`` si illisible/incohérente."""
    emprise = coins_emprise(brut)
    if emprise is None or not (emprise['ouest'] < emprise['est']
                               and emprise['sud'] < emprise['nord']):
        return None
    return emprise


def _lnglat(point, emprise):
    fx, fy = point  # fractions de l'image, origine en haut à gauche
    return [emprise['ouest'] + fx * (emprise['est'] - emprise['ouest']),
            emprise['nord'] - fy * (emprise['nord'] - emprise['sud'])]


def _enveloppe(points):
    """Enveloppe convexe (chaîne monotone) : le contour d'ensemble proposé."""
    points = sorted({tuple(p) for p in points})
    if len(points) < 3:
        return [list(p) for p in points]

    def demi(suite):
        bord = []
        for p in suite:
            while len(bord) >= 2 and ((bord[-1][0] - bord[-2][0]) * (p[1] - bord[-2][1])
                                      - (bord[-1][1] - bord[-2][1]) * (p[0] - bord[-2][0])) <= 0:
                bord.pop()
            bord.append(p)
        return bord[:-1]
    return [list(p) for p in demi(points) + demi(reversed(points))]


@functools.lru_cache(maxsize=1)
def _types_obstacle():
    """Les types d'obstacle de l'atelier : l'enum du schéma du document, lue au chargement."""
    with open(_SCHEMA_LAYOUT, encoding='utf-8') as fichier:
        schema = json.load(fichier)
    return frozenset(schema['$defs']['obstacle']['properties']['type']['enum'])


def projeter_obstacles(data, emprise):
    """ACAL1049 — les obstacles du fournisseur, projetés comme les pans.

    Seuls les types de l'atelier sont servis : un autre est ÉCARTÉ et journalisé
    (``propositions.obstacles[i].type``), sans rien faire perdre d'autre. La forme
    est déjà garantie par ``valider_obstacles`` (côté fournisseur). Jamais une pose.
    """
    servis = []
    for rang, obstacle in enumerate(data.get('obstacles') or []):
        if obstacle['type'] not in _types_obstacle():
            logger.info("propositions.obstacles[%d].type : « %s » n'est pas un type de l'atelier, "
                        "obstacle écarté", rang, obstacle['type'])
            continue
        servis.append({'type': obstacle['type'], 'confiance': obstacle['confiance'],
                       'contour_lnglat': [_lnglat(p, emprise) for p in obstacle['sommets']]})
    return servis


def detecter(company_id, contenu, mime, emprise):
    """Propositions ``{contour_lnglat, pans, obstacles}`` ; lève ``DetectionIndisponible``."""
    from core.ai.fournisseurs_claude import valider_pans
    from core.ai.usage import usage_context

    fournisseur = _fournisseur(company_id)
    if fournisseur is None:
        raise DetectionIndisponible
    with usage_context(company_id=company_id, feature_key=FEATURE):
        resultat = fournisseur.detecter(content=contenu, mime_type=mime)
    pans = valider_pans(resultat.data)[0] if resultat.ok and isinstance(resultat.data, dict) else None
    if not pans:
        raise DetectionIndisponible
    pans = [{'contour_lnglat': [_lnglat(p, emprise) for p in pan['sommets']],
             'azimut_deg': None, 'confiance': pan['confiance']} for pan in pans]
    contour = _enveloppe([p for pan in pans for p in pan['contour_lnglat']])
    return {'contour_lnglat': contour, 'pans': pans,
            'obstacles': projeter_obstacles(resultat.data, emprise)}
