"""ACAL426 — « Générer le devis » dit quelles pentes et quelles faces n'ont
jamais été confirmées (D-ACAL-7, zéro chiffre inventé).

Fonction PURE sur le ``layout`` : un avertissement par pan et par hypothèse,
jamais un blocage. Les clés lues sont celles du schéma ``roof_layout_v2`` :
``zones[].pitchDeg`` / ``pitchSource`` / ``roofType`` / ``facingAzimuthDeg`` /
``facingManual`` / ``facingAzimuthSource``. Rien n'est écrit.
"""
from __future__ import annotations

from .valeurs import nombre as _nombre


def avertissements_hypotheses(layout):
    """Messages (liste de chaînes) des pentes / faces jamais confirmées."""
    if not isinstance(layout, dict):
        return []
    zones = next((layout[c] for c in ('zones', 'areas', 'pans')
                  if isinstance(layout.get(c), list)), [])
    messages = []
    for rang, zone in enumerate(zones, 1):
        if not isinstance(zone, dict) or zone.get('roofType') == 'flat':
            continue
        nom = zone.get('label') or zone.get('id') or rang
        pente = _nombre(zone.get('pitchDeg'))
        if pente and pente > 0 and not zone.get('pitchSource'):
            messages.append(f"Pan « {nom} » : la pente ({pente:g}°) n'a "
                            "jamais été confirmée — confirmez-la avant "
                            "d'envoyer le devis.")
        face = _nombre(zone.get('facingAzimuthDeg'))
        if face is not None and not (zone.get('facingManual') is True
                                     or zone.get('facingAzimuthSource')):
            messages.append(f"Pan « {nom} » : la face ({face:g}°) n'a "
                            "jamais été confirmée — confirmez-la avant "
                            "d'envoyer le devis.")
    return messages
