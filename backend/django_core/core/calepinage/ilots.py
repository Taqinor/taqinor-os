# -*- coding: utf-8 -*-
"""CIQ137 — découpage du champ en ÎLOTS bornés avec allées coupe-feu.

Un grand toit était pavé d'un seul tenant ; une bande coupe-feu ne pouvait
être que DESSINÉE à la main comme zone interdite (AOF36). Quand le projet
déclare ``contraintes_site.ilot_max_m`` (CIQ136, ex. FM Global DS 1-15 :
champs ≤ 46 × 46 m, allées de 1,2 m), chaque pan est partitionné en îlots
≤ longueur × largeur, séparés par des allées ``allee_ilot_m`` : les allées
deviennent des zones ``INTERDITE`` du moteur — la pose, le comptage ET la
validation les respectent donc par construction (aucune seconde règle).

La MÊME grille sert la contenance du devis (``apps.ventes.calepinage_options
.capacite_du_layout``) par :func:`module_hors_allees` : un îlot commence au
bord bas de la boîte du pan sur chaque axe, dans le repère métrique du pan.

Sans contrainte ⇒ aucune zone, aucun module retiré : octet-identique.
Noyau PUR (stdlib + paquet).
"""

from core.calepinage.types import NatureZone, Zone

__all__ = [
    "bandes_allees", "zones_allees", "module_hors_allees", "regle_ilots",
    "lire_contraintes",
]

#: Débord des zones d'allée au-delà de la boîte du pan (m) : une allée doit
#: traverser le pan de part en part, jamais s'arrêter à un bord arrondi.
_DEBORD_M = 1.0


def lire_contraintes(contraintes):
    """``(longueur, largeur, allee, source)`` ou ``None`` (pas d'îlot)."""
    ilot = (contraintes or {}).get('ilot_max_m') or None
    if not isinstance(ilot, dict):
        return None
    try:
        longueur = float(ilot.get('longueur'))
        largeur = float(ilot.get('largeur'))
        allee = float((contraintes or {}).get('allee_ilot_m') or 0.0)
    except (TypeError, ValueError):
        return None
    if longueur <= 0 or largeur <= 0 or allee < 0:
        return None
    source = ((contraintes or {}).get('source') or {})
    regles = ((contraintes or {}).get('regles') or {})
    citation = regles.get('ilot_max_m') or ' '.join(
        x for x in (source.get('document'), source.get('reference')) if x)
    return longueur, largeur, allee, citation


def bandes_allees(debut, fin, taille_ilot, allee):
    """Les intervalles ``(a, b)`` d'allée STRICTEMENT dans ``[debut, fin]``.

    Îlot i : ``[debut + i·(taille+allée), … + taille]`` ; l'allée le suit.
    """
    if allee <= 0 or taille_ilot <= 0 or fin <= debut:
        return ()
    bandes = []
    pas = taille_ilot + allee
    a = debut + taille_ilot
    while a < fin - 1e-9:
        bandes.append((a, min(a + allee, fin)))
        a += pas
    return tuple(bandes)


def zones_allees(repere, bornes, longueur, largeur, allee):
    """Zones ``INTERDITE`` des allées d'îlots d'un pan.

    ``bornes`` = ``(xmin, xmax, ymin, ymax)`` du pan dans le repère moteur
    (x le long des rangées). ``longueur`` borne l'îlot le long de x,
    ``largeur`` le long de y.
    """
    xmin, xmax, ymin, ymax = bornes
    zones = []
    for i, (a, b) in enumerate(bandes_allees(xmin, xmax, longueur, allee)):
        zones.append(Zone(
            repere='%s_ALLEE_X%d' % (repere, i + 1),
            nature=NatureZone.INTERDITE,
            sommets=((a, ymin - _DEBORD_M), (b, ymin - _DEBORD_M),
                     (b, ymax + _DEBORD_M), (a, ymax + _DEBORD_M))))
    for i, (a, b) in enumerate(bandes_allees(ymin, ymax, largeur, allee)):
        zones.append(Zone(
            repere='%s_ALLEE_Y%d' % (repere, i + 1),
            nature=NatureZone.INTERDITE,
            sommets=((xmin - _DEBORD_M, a), (xmax + _DEBORD_M, a),
                     (xmax + _DEBORD_M, b), (xmin - _DEBORD_M, b))))
    return tuple(zones)


def _chevauche(debut, fin, bandes):
    return any(debut < b - 1e-9 and fin > a + 1e-9 for a, b in bandes)


def module_hors_allees(rect, bornes, longueur, largeur, allee):
    """Le module ``(x0, x1, y0, y1)`` échappe-t-il à toute allée d'îlot ?

    La MÊME grille que :func:`zones_allees` (même origine : la boîte du pan).
    """
    xmin, xmax, ymin, ymax = bornes
    x0, x1, y0, y1 = rect
    if _chevauche(x0, x1, bandes_allees(xmin, xmax, longueur, allee)):
        return False
    return not _chevauche(y0, y1, bandes_allees(ymin, ymax, largeur, allee))


def regle_ilots(longueur, largeur, allee, citation=''):
    """La phrase PUBLIÉE de la règle d'îlots, avec la source du projet."""
    phrase = ('Îlots ≤ %.1f × %.1f m, allées de %.2f m entre îlots'
              % (longueur, largeur, allee))
    return '%s (%s)' % (phrase, citation) if citation else phrase
