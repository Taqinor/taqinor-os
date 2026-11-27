"""ACAL835 — le plus petit nombre de panneaux qui atteint une COUVERTURE visée.

La couverture est celle du bilan horaire (règle COUV-AUTO,
``autoconsommation.bilan_autoconsommation`` → ``taux_couverture`` : la part
AUTOCONSOMMÉE de la consommation) — le SEUL calcul de la couverture. Elle croît
avec le nombre de panneaux (``min(charge, production)`` ne décroît jamais quand
la production monte) : une dichotomie sur 1..N0 suffit. La production de N
modules est celle de la série stockée × N ÷ N0 (``MENTION_HYPOTHESE``).
"""
from __future__ import annotations

from . import autoconsommation as _bilan
from .balayage import BalayageInvalide
from .etapes import FACTEURS_KW, ORDRE_COLONNES_ENERGIE

MENTION_HYPOTHESE = (
    "production proportionnelle au nombre de modules ; l'ombrage propre à "
    "chaque module retiré n'est pas rejoué")
_EPSILON = 1e-9


def _couverture_pct(charge, production, nombre, n0):
    """Couverture (%) de ``nombre`` modules sur les ``n0`` posés."""
    bilan = _bilan.bilan_autoconsommation(
        charge, [p * nombre / n0 for p in production])
    return round(100.0 * bilan['taux_couverture'], 2)


def plus_petit_nombre_pour_couverture(charge, production, n0, cible_pct):
    """``{nombre_modules, couverture_pct, atteint, maximum}`` : le plus petit
    N de 1..n0 dont la couverture atteint ``cible_pct`` ; sinon
    ``atteint=False`` et le maximum (les n0 posés) dit ce qu'ils couvrent."""
    maximum = {'nombre_modules': n0,
               'couverture_pct': _couverture_pct(charge, production, n0, n0)}
    if maximum['couverture_pct'] + _EPSILON < cible_pct:
        return {'nombre_modules': None, 'couverture_pct': maximum[
            'couverture_pct'], 'atteint': False, 'maximum': maximum}
    bas, haut = 1, n0
    while bas < haut:
        milieu = (bas + haut) // 2
        if _couverture_pct(charge, production, milieu, n0) + _EPSILON >= cible_pct:
            haut = milieu
        else:
            bas = milieu + 1
    return {'nombre_modules': bas, 'atteint': True, 'maximum': maximum,
            'couverture_pct': _couverture_pct(charge, production, bas, n0)}


def lire_socle(servi, serie, n0):
    """``(charge, production)`` horaires de la simulation STOCKÉE, ou un refus
    nommé (409) : absente, périmée, agrégée au jour, avec batterie (elle
    déplace l'énergie), sans consommation, sans production, sans module."""
    def refus(motif, champ='simulation'):
        return BalayageInvalide(motif, champ=champ)

    points = (serie or {}).get('points') or []
    if not (servi or {}).get('simule') or not points:
        raise refus('Aucune simulation à jour : lancez la simulation.')
    if servi.get('simulation_perimee'):
        raise refus(servi.get('motif') or 'La simulation est périmée.')
    if serie.get('tronquee'):
        raise refus("La série est agrégée au jour : le bilan horaire n'est "
                    'pas lisible. Passez la fenêtre météo à une année '
                    '(Réglages simulation) pour dimensionner par objectif.')
    if not isinstance(n0, int) or n0 < 1:
        raise refus("Aucun module posé : rien à dimensionner.", 'pose')
    if any(p.get('batterie_soc_pct') is not None for p in points):
        raise refus("La batterie déplace l'énergie : la couverture visée "
                    "n'est pas cherchée avec elle.", 'electrique.batterie')
    charge = [p.get('charge_kwh') for p in points]
    if any(valeur is None for valeur in charge):
        raise refus(((servi.get('autoconsommation') or {}).get('motif'))
                    or 'Aucune consommation horaire.', 'consommation')
    nom = next((c for c in ORDRE_COLONNES_ENERGIE
                if any(p.get(c) is not None for p in points)), None)
    if nom is None:
        raise refus('Aucune production horaire lisible.', 'production')
    heures = float(serie.get('pas_minutes') or 60) / 60.0
    return charge, [max(0.0, float(p.get(nom) or 0.0)) * FACTEURS_KW[nom]
                    * heures for p in points]
