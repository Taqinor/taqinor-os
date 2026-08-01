"""AOF158 — garde-fou de CRÉDIBILITÉ des prix issus de la cascade.

Une fourchette non alimentée est un contrôle décoratif
======================================================
La cascade inverse (``cascade.resoudre_cascade``) peut techniquement produire
n'importe quel PU : si la cible est basse et les quantités fortes, elle sortira
un module à 900 DH. Techniquement juste, commercialement absurde, et
immédiatement repéré par une commission d'ouverture des plis.

Ce module compare donc chaque PU à une **fourchette par famille d'équipement**
alimentée par la bibliothèque de prix (AOF124) — jamais par des constantes
écrites ici : une fourchette codée en dur vieillit et devient un contrôle qui
ment. Chaque fourchette porte SA SOURCE (d'où vient le chiffre, à quelle date)
parce qu'un écart signalé sans source n'est pas actionnable.

Le rapport est trié par IMPACT (écart × quantité) et non par écart relatif : ce
qui compte est le nombre de dirhams en jeu, pas le pourcentage sur une ligne à
quatre unités.

Deux régimes, comme partout dans ce groupe : ``alerte`` (on signale) et
``refus`` (on bloque). Le refus est réservé aux écarts hors de toute
plausibilité, réglés par ``tolerance_refus``.
"""
from __future__ import annotations

from decimal import Decimal

__all__ = [
    'ALERTE',
    'REFUS',
    'PrixHorsBande',
    'controler_fourchettes',
    'verifier_fourchettes',
]

ALERTE = 'alerte'
REFUS = 'refus'


class PrixHorsBande(Exception):
    """Levée quand au moins un PU est hors de toute plausibilité."""

    def __init__(self, ecarts):
        self.ecarts = list(ecarts)
        super().__init__(
            "Prix unitaires hors bande : "
            + ' ; '.join(
                "ligne {} ({}) PU {} hors [{} ; {}] — source {}".format(
                    e['numero'], e['famille'], e['pu'], e['min'], e['max'],
                    e['source'])
                for e in self.ecarts))


def controler_fourchettes(lignes, fourchettes, *, tolerance_refus=Decimal('2')):
    """Compare chaque PU à la fourchette de sa famille.

    Args:
        lignes: la projection ``cascade.lignes_du_bordereau``.
        fourchettes: ``{famille: {'min', 'max', 'source'}}`` — alimentée par le
            selector de bibliothèque de prix (AOF124). Une famille ABSENTE
            n'est pas une erreur : elle est simplement non couverte, et le
            rapport le dit plutôt que de la déclarer conforme.
        tolerance_refus: facteur au-delà (ou en deçà) duquel l'écart passe de
            l'alerte au refus. ``2`` = plus du double ou moins de la moitié.

    Returns:
        ``{'ecarts': [...], 'refus': [...], 'non_couvertes': [...]}`` —
        ``ecarts`` trié par impact décroissant.
    """
    ecarts = []
    non_couvertes = []
    for ligne in lignes or ():
        famille = str(ligne.get('famille') or '')
        bande = (fourchettes or {}).get(famille)
        if not bande:
            non_couvertes.append({'numero': ligne.get('numero'),
                                  'famille': famille})
            continue
        pu = Decimal(str(ligne['pu']))
        borne_min = Decimal(str(bande['min']))
        borne_max = Decimal(str(bande['max']))
        if borne_min <= pu <= borne_max:
            continue
        quantite = Decimal(str(ligne.get('quantite') or 0))
        reference = borne_max if pu > borne_max else borne_min
        impact = abs(pu - reference) * quantite
        severite = ALERTE
        if pu > borne_max * Decimal(str(tolerance_refus)) or \
                pu * Decimal(str(tolerance_refus)) < borne_min:
            severite = REFUS
        ecarts.append({
            'numero': ligne.get('numero'),
            'designation': ligne.get('designation', ''),
            'famille': famille,
            'pu': pu,
            'min': borne_min,
            'max': borne_max,
            'source': bande.get('source', ''),
            'quantite': quantite,
            'impact': impact,
            'severite': severite,
        })
    ecarts.sort(key=lambda e: e['impact'], reverse=True)
    return {
        'ecarts': ecarts,
        'refus': [e for e in ecarts if e['severite'] == REFUS],
        'non_couvertes': non_couvertes,
    }


def verifier_fourchettes(lignes, fourchettes, **options):
    """Porte : lève ``PrixHorsBande`` si un PU est hors de toute plausibilité.

    Les simples alertes sont RENVOYÉES, pas levées : un PU 10 % au-dessus de
    la bande est une décision commerciale, pas une erreur.
    """
    rapport = controler_fourchettes(lignes, fourchettes, **options)
    if rapport['refus']:
        raise PrixHorsBande(rapport['refus'])
    return rapport
