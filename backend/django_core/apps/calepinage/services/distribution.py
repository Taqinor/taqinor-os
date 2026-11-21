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
           'histogramme_puissance']

#: Convention d'AFFICHAGE (classes de 5 % de la puissance AC, comme la
#: distribution de PVsyst) : une classe = un vingtième de la borne. Aucun
#: calcul de perte ne la lit — ce n'est pas un seuil technique.
CLASSES_PAR_BORNE = 20

MOTIF_SANS_PRODUCTION = ("Aucune heure de production dans la série : la "
                         "distribution de puissance n'est pas tracée.")


def histogramme_puissance(puissances_kw, borne_kw, pas_minutes):
    """``{borne_kw, largeur_kw, classes, energie_totale_kwh,
    energie_ecretee_kwh, part_ecretee_pct}`` ou ``None`` (aucune heure > 0).

    Les classes sont alignées sur la borne (elle est une frontière de classe) ;
    seules les heures de puissance > 0 comptent ; les classes vides sont omises.
    """
    from .electrique import ecretage_depuis_serie

    borne = nombre(borne_kw)
    heures = float(pas_minutes) / 60.0
    actives = [p for p in (nombre(v) for v in puissances_kw or ())
               if p is not None and p > 0.0]
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
            sum(max(0.0, p - borne) for p in actives) * heures, 3),
        'part_ecretee_pct': ecretage_depuis_serie(actives, borne),
    }
