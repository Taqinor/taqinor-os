"""CAL138 — les PANS du document de pose, avec orientation et inclinaison.

ACAL329 — ``production_du_layout`` (un appel PVGIS ``pvcalculation=1`` par
pan, pertes PASSÉES à PVGIS) est SUPPRIMÉE : ce modèle est abandonné, la
production du module a UN seul producteur, ``services/chaine_pertes.py``
(irradiance NUE de ``ClientPvgis.serie_irradiance`` puis chaque poste de
perte appliqué par la cascade). Reste ici la lecture des pans, consommée par
``asbuilt``, ``lestage``, ``reglementaire`` et la présentation compacte. Le
texte ci-dessous décrit la règle d'origine (CAL138), dont la lecture des pans
reste fidèle.

LE CONSTAT
----------
La production du devis repose sur un productible de VILLE
(``frontend/src/features/ventes/solar.js``, table ``PRODUCTIBLE_PAR_VILLE``,
défaut Casablanca) : un seul chiffre pour toute la ville, quelle que soit
l'orientation du toit. Or le calepinage CONNAÎT la pente et l'azimut de chaque
pan (``zones[].geometry.tiltDeg`` / ``azimuthDeg`` du document ``roof_layout``
v2). PVsyst autorise d'ailleurs jusqu'à 8 orientations dans une variante.

LA RÈGLE POSÉE ICI
------------------
1. **Un appel PVGIS par PLAN réel** (angle + azimut du pan), jamais un azimut
   moyen : la moyenne de deux pans opposés est un toit qui n'existe pas.
2. **Le total est la SOMME des pans**, au prorata des modules réellement
   posés. Il ne peut donc pas diverger du détail affiché.
3. **Un pan sans module ne pèse rien** : aucun appel, aucune production — et
   ``p50_kwh`` vaut ``null``, jamais ``0`` (un 0 se lirait « ce pan ne produit
   rien », là où personne n'a rien posé dessus).
4. **Rien n'est inventé.** P75/P90 et la variabilité inter-annuelle ne sont
   PAS calculés ici (c'est CAL142) : ils valent ``null`` et la raison est
   publiée dans ``avertissements``. L'ombrage par pan n'est pas mesuré ici non
   plus.
5. **Les pertes sont celles de CAL238** : la somme explicite passée à PVGIS,
   republiée avec le résultat.

La forme rendue est celle du contrat committé
``contract_samples/calepinage_resultat.json`` (blocs ``production`` et
``pertes``) — aucune clé inventée.
"""
from __future__ import annotations
from .valeurs import nombre as _nombre

__all__ = ['pans_du_layout']


def _premier(*valeurs):
    for valeur in valeurs:
        nombre = _nombre(valeur)
        if nombre is not None:
            return nombre
    return None


def pans_du_layout(layout):
    """Les pans d'un document ``roof_layout`` v2, prêts à être interrogés.

    Lit ``zones[]`` : la géométrie POSÉE (``geometry``) prime sur le résultat
    d'écran (``result``), qui prime sur le dimensionnement souhaité
    (``neededPanels``) — même ordre de préséance que les lecteurs existants du
    document. Aucune valeur par défaut n'est inventée : un pan sans
    orientation est rendu tel quel, avec ses champs à ``None``.
    """
    zones = ((layout or {}).get('zones')
             if isinstance(layout, dict) else None) or []
    pans = []
    for rang, zone in enumerate(zones):
        if not isinstance(zone, dict):
            continue
        geometrie = zone.get('geometry') if isinstance(
            zone.get('geometry'), dict) else {}
        resultat = zone.get('result') if isinstance(
            zone.get('result'), dict) else {}
        modules = _premier(geometrie.get('count'), resultat.get('count'), 0)
        pans.append({
            'pan': str(zone.get('label') or zone.get('id')
                       or f'PAN-{rang + 1}'),
            'modules': int(modules or 0),
            'kwc': _premier(geometrie.get('kwc'), resultat.get('kwc')),
            'azimut_deg': _premier(geometrie.get('azimuthDeg'),
                                   zone.get('facingAzimuthDeg')),
            'inclinaison_deg': _premier(geometrie.get('tiltDeg'),
                                        zone.get('pitchDeg')),
        })
    return pans
