"""CAL142 — P50/P90 pour un calepinage, MÊME SANS DEVIS, sans second moteur.

LE CONSTAT
----------
``simulate_bankable_yield`` (``apps/ventes/solar_design.py``) existe déjà et
n'était atteignable que par le parcours DEVIS : un calepinage autonome — une
toiture conçue avant tout chiffrage — n'avait aucun P90. PVsyst, lui, en fait
un outil de projet à part entière
(https://www.pvsyst.com/help/project-design/p50-p90-evaluations.html).

LA RÈGLE POSÉE ICI
------------------
1. **UN SEUL moteur de statistiques.** On appelle celui de ``ventes``, on n'en
   écrit pas un second : deux lois normales dans le même dépôt finiraient par
   donner deux P90 pour la même toiture.
2. **AUCUNE PERTE N'EST APPLIQUÉE DEUX FOIS.** La production du module sort
   déjà de PVGIS avec la somme explicite des postes de CAL139 (``loss``,
   CAL238). On passe donc au moteur des facteurs de perte TOUS À ZÉRO : il ne
   fait plus que la statistique (P50 = base, puis les quantiles). Lui laisser
   ses postes par défaut retrancherait une seconde fois 8 % de thermique et
   3 % de salissure sur une production qui les porte déjà.
3. **σ EST MESURÉ QUAND C'EST POSSIBLE.** Si la fenêtre ``seriescalc`` couvre
   plusieurs années, σ est l'écart-type RELATIF des productions annuelles
   réellement observées, et son origine le dit (``mesuree``, avec le nombre
   d'années). Une seule année ⇒ aucun écart-type n'est mesurable : on emploie
   la variabilité de référence du moteur de ventes, ANNONCÉE comme hypothèse.

Module PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

import statistics

# Le moteur de statistiques de ``ventes`` est un module PUR (aucun modèle,
# aucune base) — c'est le même patron que ``services/pompage.py``, qui lit
# déjà ``apps.ventes.solar_design.pumping_cycle_yield``.
from apps.ventes.solar_design import (
    DEFAULT_ANNUAL_VARIABILITY, simulate_bankable_yield,
)

__all__ = ['ORIGINE_HYPOTHESE', 'ORIGINE_MESUREE', 'bankable',
           'variabilite_interannuelle']

ORIGINE_MESUREE = 'mesuree'
ORIGINE_HYPOTHESE = 'hypothese'


def _pertes_neutralisees():
    """Les postes du moteur de ventes, TOUS À ZÉRO.

    La production qu'on lui donne porte DÉJÀ ses pertes (CAL139/CAL238). La
    liste est relue dans le moteur plutôt que recopiée : un poste ajouté
    là-bas est neutralisé ici aussi, sans quoi il réapparaîtrait en douce
    dans notre P50.
    """
    from apps.ventes.solar_design import DEFAULT_LOSS_FACTORS as _postes
    return {poste: 0.0 for poste in _postes}


def variabilite_interannuelle(totaux_par_annee):
    """σ RELATIF mesuré sur les productions annuelles, ou rien.

    Args:
        totaux_par_annee: ``{annee: kWh}`` — les totaux RÉELLEMENT observés
            dans la fenêtre demandée à PVGIS.

    Returns:
        ``(sigma, origine, annees)``. Moins de deux années complètes ⇒
        ``(None, 'hypothese', n)`` : un écart-type sur une seule valeur n'a
        pas de sens, et en fabriquer un serait un chiffre inventé.
    """
    valeurs = [float(v) for v in (totaux_par_annee or {}).values()
               if v is not None and float(v) > 0]
    if len(valeurs) < 2:
        return None, ORIGINE_HYPOTHESE, len(valeurs)
    moyenne = sum(valeurs) / len(valeurs)
    if moyenne <= 0:
        return None, ORIGINE_HYPOTHESE, len(valeurs)
    return (statistics.stdev(valeurs) / moyenne, ORIGINE_MESUREE,
            len(valeurs))


def bankable(p50_kwh, *, totaux_par_annee=None, kwc=None):
    """P50 / P75 / P90 d'une production déjà nette de ses pertes.

    Args:
        p50_kwh: la production annuelle du calepinage (déjà amputée des
            pertes de CAL139, puisqu'elles sont parties dans la requête PVGIS).
        totaux_par_annee: ``{annee: kWh}`` pour MESURER σ. Absent ou d'une
            seule année ⇒ σ d'hypothèse, annoncé comme tel.
        kwc: la puissance crête, pour le rendement spécifique.

    Returns:
        dict — ``p50_kwh``, ``p75_kwh``, ``p90_kwh``,
        ``annual_variability`` (σ employé), ``sigma_source``
        (``mesuree``/``hypothese``), ``sigma_annees``,
        ``specific_yield_kwh_kwc``, ``commentaire``.
        ``p50_kwh`` absent ou ≤ 0 ⇒ toutes les sorties valent ``None`` (jamais
        des zéros, qui se liraient « la toiture ne produit rien »).
    """
    try:
        base = float(p50_kwh) if p50_kwh is not None else None
    except (TypeError, ValueError):
        base = None
    if base is None or base <= 0:
        return {
            'p50_kwh': None, 'p75_kwh': None, 'p90_kwh': None,
            'annual_variability': None, 'sigma_source': None,
            'sigma_annees': 0, 'specific_yield_kwh_kwc': None,
            'commentaire': (
                "Aucune production n'a été simulée : P50, P75 et P90 restent "
                '« non calculés », jamais 0.'),
        }

    sigma, origine, annees = variabilite_interannuelle(totaux_par_annee)
    if sigma is None:
        sigma = DEFAULT_ANNUAL_VARIABILITY
        commentaire = (
            'σ = variabilité interannuelle de RÉFÉRENCE '
            f'({round(sigma * 100, 1)} %), employée comme HYPOTHÈSE : la '
            f'fenêtre demandée ne couvre que {annees} année(s), et un '
            "écart-type ne se mesure pas sur une seule valeur.")
    else:
        commentaire = (
            'σ MESURÉ sur les productions annuelles réellement observées '
            f'({annees} années de la fenêtre PVGIS) : '
            f'{round(sigma * 100, 2)} %.')

    resultat = simulate_bankable_yield(
        base,
        # Les pertes sont DÉJÀ dans ``base`` (CAL238) : on neutralise celles
        # du moteur de ventes pour ne pas les compter deux fois.
        loss_factors=_pertes_neutralisees(),
        annual_variability=sigma, kwc=kwc, include_p75=True)
    return {
        'p50_kwh': resultat['p50_kwh'],
        'p75_kwh': resultat['p75_kwh'],
        'p90_kwh': resultat['p90_kwh'],
        'annual_variability': resultat['annual_variability'],
        'sigma_source': origine,
        'sigma_annees': annees,
        'specific_yield_kwh_kwc': resultat['specific_yield_kwh_kwc'],
        'commentaire': commentaire,
    }
