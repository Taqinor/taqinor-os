"""ACAL736 — l'énergie par classe de puissance demandée à l'onduleur.

Fonction PURE : à partir des puissances AVANT plafonnement (celles que l'étape
``ecretage`` lit), l'histogramme de l'énergie par classe, l'énergie écrêtée et
sa part. La part est celle de ``electrique.ecretage_depuis_serie`` (une seule
formule d'écrêtage dans le dépôt), jamais recalculée ici.

Référence : PVsyst, « Inverter array sizing » — distribution de la puissance
et perte d'écrêtage
(https://www.pvsyst.com/help/project-design/grid-connected-system-definition/inverter-array-sizing.html).
"""
from __future__ import annotations

import math

from .valeurs import nombre

__all__ = ['CLASSES_PAR_BORNE', 'MOTIF_SANS_PRODUCTION',
           'histogramme_puissance', 'part_ecretee_pct']

#: Convention d'AFFICHAGE (classes de 5 % de la puissance AC, comme la
#: distribution de PVsyst) : une classe = un vingtième de la borne. Aucun
#: calcul de perte ne la lit — ce n'est pas un seuil technique.
CLASSES_PAR_BORNE = 20

MOTIF_SANS_PRODUCTION = ("Aucune heure de production dans la série : la "
                         "distribution de puissance n'est pas tracée.")


def part_ecretee_pct(puissances_kw, bornes_kw):
    """Perte ÷ total des heures > 0, chaque heure contre SA borne (3 décimales)."""
    total = perdu = 0.0
    for valeur, borne in zip(puissances_kw, bornes_kw):
        puissance = nombre(valeur)
        if puissance is None or puissance <= 0.0:
            continue
        total += puissance
        perdu += max(0.0, puissance - borne)
    return round(perdu / total * 100.0, 3) if total > 0.0 else None


def histogramme_puissance(puissances_kw, borne_kw, pas_minutes,
                          bornes_horaires_kw=None):
    """``{borne_kw, largeur_kw, classes, energie_totale_kwh,
    energie_ecretee_kwh, part_ecretee_pct}`` ou ``None`` (aucune heure > 0).

    Les classes sont alignées sur la borne (elle est une frontière de classe) ;
    seules les heures de puissance > 0 comptent ; les classes vides sont omises.
    ``bornes_horaires_kw`` (ACAL740, optionnel, même longueur que les
    puissances) : l'énergie écrêtée et sa part se mesurent contre la borne de
    CHAQUE heure ; les classes restent alignées sur ``borne_kw``.
    """
    from .electrique import ecretage_depuis_serie

    borne = nombre(borne_kw)
    heures = float(pas_minutes) / 60.0
    bornes = list(bornes_horaires_kw) if bornes_horaires_kw else None
    couples = [(p, bornes[i] if bornes else borne)
               for i, p in enumerate(nombre(v) for v in puissances_kw or ())
               if p is not None and p > 0.0]
    actives = [p for p, _ in couples]
    if not actives or borne is None or borne <= 0.0:
        return None
    largeur = borne / CLASSES_PAR_BORNE
    energies = {}
    for puissance in actives:
        # ``round`` : 0,3 / 0,1 vaut 2,999…, la classe reste la 3e.
        rang = math.floor(round(puissance / largeur, 9))
        energies[rang] = energies.get(rang, 0.0) + puissance * heures
    return {
        'borne_kw': round(borne, 3),
        'largeur_kw': round(largeur, 6),
        'classes': [{'de_kw': round(rang * largeur, 3),
                     'a_kw': round((rang + 1) * largeur, 3),
                     'energie_kwh': round(energies[rang], 3)}
                    for rang in sorted(energies)],
        'energie_totale_kwh': round(sum(actives) * heures, 3),
        'energie_ecretee_kwh': round(
            sum(max(0.0, p - b) for p, b in couples) * heures, 3),
        'part_ecretee_pct': (
            part_ecretee_pct(*zip(*couples)) if bornes
            else ecretage_depuis_serie(actives, borne)),
    }
