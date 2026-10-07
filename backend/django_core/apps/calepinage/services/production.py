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

__all__ = ['cle_de_pan', 'numeros_des_modules', 'cle_de_module',
           'cles_des_pans', 'cles_des_modules']


# ── ACAL265 (C-ACAL-051) — LA clé STABLE d'un pan et d'un module ───────────
#
# Six recopies « label, sinon id, sinon PAN-<rang> » nommaient les pans par
# leur LIBELLÉ : renommer un pan détachait l'affectation manuelle, le
# cheminement et la pose réelle stockés sous l'ancien nom. La clé d'un pan
# est désormais son ``zone.id`` (le libellé reste un AFFICHAGE, à part) ; le
# repli ``PAN-<rang>`` ne sert qu'à un pan sans id. La clé d'un module est
# ``<clé du pan>#<n>`` où ``n`` est le numéro STABLE du panneau
# (``geometry.panels[].n``) — le rang 1…N seulement pour un document ancien
# jamais numéroté.

def cle_de_pan(zone, rang):
    """``zone.id`` — ``'PAN-<rang>'`` seulement pour un pan sans id."""
    zone = zone if isinstance(zone, dict) else {}
    return str(zone.get('id') or 'PAN-%d' % rang)


def numeros_des_modules(geometrie):
    """Les numéros STABLES (``panels[].n``) des modules, dans l'ordre du
    document — ``()`` quand un panneau n'en porte pas (document ancien) ou
    quand deux panneaux portent le même (le rang reprend alors la main)."""
    panneaux = (geometrie.get('panels') if isinstance(geometrie, dict)
                else None)
    if not isinstance(panneaux, (list, tuple)) or not panneaux:
        return ()
    numeros = []
    for panneau in panneaux:
        numero = panneau.get('n') if isinstance(panneau, dict) else None
        if isinstance(numero, bool) or not isinstance(numero, int) \
                or numero <= 0:
            return ()
        numeros.append(numero)
    if len(set(numeros)) != len(numeros):
        return ()
    return tuple(numeros)


def cle_de_module(cle_pan, rang, numeros=()):
    """``'<clé du pan>#<n>'`` — ``n`` le numéro stable du ``rang``-ième
    module (1…N), sinon le rang lui-même."""
    numero = (numeros[rang - 1] if numeros and 0 < rang <= len(numeros)
              else rang)
    return '%s#%d' % (cle_pan, numero)


def _zones(layout):
    zones = ((layout.get('zones') or layout.get('areas')
              or layout.get('pans') or []) if isinstance(layout, dict)
             else [])
    return zones if isinstance(zones, list) else []


def cles_des_pans(layout):
    """Les clés STABLES des pans, ALIGNÉES sur
    ``apps.ventes.services.pans_du_document`` (même ordre, une par pan) :
    toits d'abord (``cle_de_pan``), puis surfaces de pose (``id``, sinon
    ``surface-<rang>`` — la clé de la primitive)."""
    cles = [cle_de_pan(zone, rang)
            for rang, zone in enumerate(_zones(layout), start=1)
            if isinstance(zone, dict)]
    surfaces = (layout.get('poseSurfaces') if isinstance(layout, dict)
                else None)
    for rang, surface in enumerate(
            surfaces if isinstance(surfaces, list) else [], start=1):
        if isinstance(surface, dict):
            cles.append(str(surface.get('id') or 'surface-%d' % rang))
    return cles


def cles_des_modules(layout):
    """``{clé du pan: (numéros stables)}`` des pans de toit du document."""
    return {cle_de_pan(zone, rang): numeros_des_modules(zone.get('geometry'))
            for rang, zone in enumerate(_zones(layout), start=1)
            if isinstance(zone, dict)}


def _pans_du_layout(layout):
    """Les pans d'un document ``roof_layout`` v2, prêts à être interrogés.

    ACAL61 — adaptateur MINCE de ``apps.ventes.services.pans_du_document``
    (LA primitive, D-ACAL-5) : pans de toit ET surfaces de pose (champ au
    sol, ombrière), compte POSÉ (``neededPanels`` n'est jamais posé : un pan
    non pavé rend 0 module), orientation de ``orientation_du_pan``. Aucune
    valeur par défaut n'est inventée : un pan sans orientation est rendu tel
    quel, ses champs à ``None``.
    """
    from apps.ventes.services import pans_du_document

    return [{
        # ACAL265 — la clé STABLE à part, le libellé n'est qu'un affichage.
        'cle': cle,
        'pan': str(pan.get('libelle')),
        'modules': int(pan.get('modules') or 0),
        'kwc': _nombre(pan.get('kwc')),
        'azimut_deg': _nombre(pan.get('azimut_deg')),
        'inclinaison_deg': _nombre(pan.get('inclinaison_deg')),
    } for pan, cle in zip(pans_du_document(layout), cles_des_pans(layout))]
