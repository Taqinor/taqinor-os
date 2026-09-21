"""CAL142 / CALX184-186 — P50/P90/P95 d'un calepinage, MÊME SANS DEVIS.

LE CONSTAT (CAL142)
-------------------
``simulate_bankable_yield`` (``apps/ventes/solar_design.py``) existe déjà et
n'était atteignable que par le parcours DEVIS : un calepinage autonome — une
toiture conçue avant tout chiffrage — n'avait aucun P90. PVsyst, lui, en fait
un outil de projet à part entière
(https://www.pvsyst.com/help/project-design/p50-p90-evaluations.html).

CE QUE CALX184 CHANGE : MESURER σ, OU REFUSER
----------------------------------------------
Jusqu'ici, dès que la fenêtre météo ne portait pas deux années, ce module
retombait sur la variabilité de référence du moteur de ventes
(``apps/ventes/solar_design.py``) et l'étiquetait « hypothèse ». Ce littéral
n'a AUCUNE citation dans le dépôt : un P90 bâti dessus est un chiffre
d'apparence bancable tiré d'une constante sans origine, ce que la décision
D-CALX 7 interdit. Le repli est SUPPRIMÉ.

TROIS ORIGINES ADMISES POUR σ, JAMAIS UNE QUATRIÈME — c'est la doctrine de
HelioScope, qui fait venir la variabilité soit des données interannuelles de
la source météo, soit d'une publication nommée, soit d'une valeur fournie par
l'utilisateur, et trace les trois
(https://help-center.helioscope.com/hc/en-us/articles/39323166747667-P90-P95-and-P99-Values-Accuracy-Study) :
σ MESURÉ sur au moins deux années de la fenêtre, σ SAISI par la société avec
sa provenance (réglages CALX145), ou RIEN — et « rien » se lit dans le
résultat, en français, au lieu d'un chiffre qui ment.

CE QUE CALX185 CHANGE : σ EST COMPOSÉ, PAS UNIQUE
---------------------------------------------------
La variabilité météo n'est plus le seul écart-type : ``services/incertitude.py``
compose EN QUADRATURE toutes les composantes sourcées (variabilité
interannuelle, incertitude de simulation, biais long terme de la source
météo), comme une étude bancable PVsyst, et c'est ce ``sigma_total`` que ce
module emploie. Le détail « de quoi σ est fait » se lit dans le bloc
``incertitude`` du résultat, pas dans un commentaire de code.

CE QUE CALX186 CHANGE : LE QUANTILE EST UNE FONCTION, ET P95 EXISTE
---------------------------------------------------------------------
Le moteur de ``ventes`` ne déclare que deux quantiles (``Z_P90``, ``Z_P75``),
une table à deux entrées : aucun autre n'y était calculable. Les quantiles du
calepinage viennent donc maintenant de ``services/incertitude.py``, qui les
déduit de ``sigma_total`` par la fonction quantile de la loi normale — ce qui
publie P95 à côté de P75 et P90 sans ajouter la moindre constante. La
continuité avec le chemin historique est TESTÉE (``test_calx186_p95.py`` :
P75 et P90 retombent sur les valeurs du moteur de ventes à 0,1 % près).
``simulate_bankable_yield`` reste le moteur du parcours DEVIS ; ce module ne
l'appelle plus.

LA RÈGLE DE CAL142 QUI RESTE, ET SE DURCIT
--------------------------------------------
**AUCUNE PERTE N'EST APPLIQUÉE DEUX FOIS.** La production donnée ici sort déjà
de PVGIS avec la somme explicite des postes de CAL139 (``loss``, CAL238). Ce
module n'applique donc AUCUN facteur de perte — plus même un jeu de facteurs
neutralisés : il ne fait que de la statistique sur une production déjà nette.

Module PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

from .incertitude import (
    CLE_SIGMA_METEO_SAISI, COMPOSANTE_METEO, IncertitudeInvalide,
    ORIGINE_ABSENTE, ORIGINE_MESUREE, ORIGINE_SAISIE, SOURCE_PVGIS,
    bloc_incertitude, sigma_mesure,
)

__all__ = ['CLE_SIGMA_METEO_SAISI', 'IncertitudeInvalide', 'ORIGINE_ABSENTE',
           'ORIGINE_MESUREE', 'ORIGINE_SAISIE', 'bankable',
           'variabilite_interannuelle']


def variabilite_interannuelle(totaux_par_annee):
    """σ RELATIF mesuré sur les productions annuelles, ou rien.

    Le calcul lui-même vit dans ``services/incertitude.py`` (CALX185), où il
    sert aussi à bâtir la composante météo du bloc publié ; cette fonction
    reste le point d'entrée historique de CAL142.

    Args:
        totaux_par_annee: ``{annee: kWh}`` — les totaux RÉELLEMENT observés
            dans la fenêtre demandée à PVGIS.

    Returns:
        ``(sigma, origine, annees)``. Moins de deux années complètes ⇒
        ``(None, 'absente', n)`` : un écart-type sur une seule valeur n'a
        pas de sens, et en fabriquer un serait un chiffre inventé.
    """
    return sigma_mesure(totaux_par_annee)


def _composante(bloc, nom):
    """La composante ``nom`` du bloc publié, ou ``None``."""
    for ligne in bloc['composantes']:
        if ligne['nom'] == nom:
            return ligne
    return None


def _commentaire_compose(bloc):
    """La phrase française qui dit DE QUOI σ est fait, sans jargon de code."""
    meteo = _composante(bloc, COMPOSANTE_METEO)
    if meteo is not None and meteo['source'] == SOURCE_PVGIS:
        tete = ('σ MESURÉ sur les productions annuelles réellement observées '
                f"({meteo['annees']} années de la fenêtre PVGIS)")
    elif meteo is not None:
        tete = f"σ SAISI par la société et sourcé ({meteo['reference']})"
    else:
        tete = 'σ SAISI par la société et sourcé'
    autres = [ligne['nom'] for ligne in bloc['composantes']
              if ligne['nom'] != COMPOSANTE_METEO]
    if autres:
        tete += ', composé en quadrature avec : ' + ', '.join(autres)
    return f"{tete} — σ total {round(bloc['sigma_total'] * 100, 2)} %."


def bankable(p50_kwh, *, totaux_par_annee=None, kwc=None, reglages=None):
    """P50 / P75 / P90 / P95 d'une production déjà nette (CAL139).

    Args:
        p50_kwh: la production annuelle du calepinage (déjà amputée des
            postes de CAL139, puisqu'ils sont partis dans la requête PVGIS).
        totaux_par_annee: ``{annee: kWh}`` pour MESURER σ. Moins de deux
            années ⇒ on se rabat sur le σ saisi, ou on refuse.
        kwc: la puissance crête, pour le rendement spécifique.
        reglages: la section ``simulation`` des réglages société (CALX145),
            d'où viennent les composantes SAISIES de σ.

    Returns:
        dict — ``p50_kwh``, ``p75_kwh``, ``p90_kwh``, ``p95_kwh``,
        ``annual_variability`` (le ``sigma_total`` composé), ``sigma_source``
        (``mesuree``/``saisie``/``absente``), ``sigma_annees``,
        ``sigma_reference``, ``specific_yield_kwh_kwc``, ``commentaire``.
        ``p50_kwh`` absent ou ≤ 0 ⇒ toutes les sorties valent ``None`` (jamais
        des zéros, qui se liraient « la toiture ne produit rien »). Aucune
        composante sourcée ⇒ P75, P90 et P95 valent ``None`` et le
        commentaire dit quoi renseigner.

    Raises:
        IncertitudeInvalide: une composante saisie sans provenance, refusée
            en nommant le réglage fautif.
    """
    try:
        base = float(p50_kwh) if p50_kwh is not None else None
    except (TypeError, ValueError):
        base = None
    if base is None or base <= 0:
        return {
            'p50_kwh': None, 'p75_kwh': None, 'p90_kwh': None,
            'p95_kwh': None,
            'annual_variability': None, 'sigma_source': None,
            'sigma_annees': 0, 'sigma_reference': '',
            'specific_yield_kwh_kwc': None,
            'commentaire': (
                "Aucune production n'a été simulée : P50, P75, P90 et P95 "
                'restent « non calculés », jamais 0.'),
        }

    bloc = bloc_incertitude(base, totaux_par_annee=totaux_par_annee,
                            reglages=reglages)
    meteo = _composante(bloc, COMPOSANTE_METEO)
    if bloc['sigma_total'] is None:
        return {
            'p50_kwh': bloc['quantiles']['p50_kwh'],
            'p75_kwh': None, 'p90_kwh': None, 'p95_kwh': None,
            'annual_variability': None, 'sigma_source': ORIGINE_ABSENTE,
            'sigma_annees': None, 'sigma_reference': '',
            'specific_yield_kwh_kwc': _rendement_specifique(base, kwc),
            'commentaire': bloc['motif_refus'],
        }

    mesuree = meteo is not None and meteo['source'] == SOURCE_PVGIS
    quantiles = bloc['quantiles']
    return {
        'p50_kwh': quantiles['p50_kwh'],
        'p75_kwh': quantiles['p75_kwh'],
        'p90_kwh': quantiles['p90_kwh'],
        'p95_kwh': quantiles['p95_kwh'],
        'annual_variability': round(bloc['sigma_total'], 4),
        'sigma_source': ORIGINE_MESUREE if mesuree else ORIGINE_SAISIE,
        'sigma_annees': meteo['annees'] if meteo is not None else None,
        'sigma_reference': meteo['reference'] if meteo is not None else '',
        'specific_yield_kwh_kwc': _rendement_specifique(base, kwc),
        'commentaire': _commentaire_compose(bloc),
    }


def _rendement_specifique(base, kwc):
    """kWh/kWc — servi même quand σ est refusé : il ne dépend pas de σ."""
    try:
        puissance = float(kwc) if kwc is not None else None
    except (TypeError, ValueError):
        return None
    if puissance is None or puissance <= 0:
        return None
    return round(base / puissance, 1)
