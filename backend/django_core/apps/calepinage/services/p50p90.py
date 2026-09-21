"""CAL142 / CALX184 — P50/P90 d'un calepinage, MÊME SANS DEVIS.

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

1. **σ MESURÉ** sur au moins deux années réellement observées dans la fenêtre
   ``seriescalc`` (``variabilite_interannuelle`` ci-dessous) ;
2. **σ SAISI** par la société avec sa provenance — le réglage de simulation
   ``sigma_meteo_saisi_pct`` (CALX145), qui porte ``{valeur, source,
   reference}`` et se refuse en NOMMANT le champ s'il n'a pas de source ;
3. **RIEN** : P75 et P90 restent « non calculés », un ``motif_refus`` en
   français dit ce qu'il faut renseigner, et AUCUNE valeur de référence ne
   vient prendre leur place.

LES DEUX AUTRES RÈGLES DE CAL142, INCHANGÉES
---------------------------------------------
* **UN SEUL moteur de statistiques.** On appelle celui de ``ventes``, on n'en
  écrit pas un second : deux lois normales dans le même dépôt finiraient par
  donner deux P90 pour la même toiture.
* **AUCUNE PERTE N'EST APPLIQUÉE DEUX FOIS.** La production du module sort
  déjà de PVGIS avec la somme explicite des postes de CAL139 (``loss``,
  CAL238). On passe donc au moteur des facteurs de perte TOUS À ZÉRO : il ne
  fait plus que la statistique. Lui laisser ses postes par défaut retrancherait
  une seconde fois le thermique et la salissure sur une production qui les
  porte déjà.

Module PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

import statistics

# Le moteur de statistiques de ``ventes`` est un module PUR (aucun modèle,
# aucune base) — c'est le même patron que ``services/pompage.py``, qui lit
# déjà ``apps.ventes.solar_design.pumping_cycle_yield``. On n'en importe PLUS
# la variabilité de repli : CALX184 la bannit de ce module.
from apps.ventes.solar_design import simulate_bankable_yield

__all__ = ['CLE_SIGMA_METEO_SAISI', 'IncertitudeInvalide', 'ORIGINE_ABSENTE',
           'ORIGINE_MESUREE', 'ORIGINE_SAISIE', 'bankable',
           'variabilite_interannuelle']

#: σ a été MESURÉ sur les productions annuelles réellement observées.
ORIGINE_MESUREE = 'mesuree'
#: σ a été SAISI par la société, avec sa provenance (réglage CALX145).
ORIGINE_SAISIE = 'saisie'
#: σ n'existe pas : ni mesuré, ni saisi. Les quantiles sont REFUSÉS.
ORIGINE_ABSENTE = 'absente'

#: Le réglage de simulation (CALX145) qui porte un σ météo saisi, en %.
CLE_SIGMA_METEO_SAISI = 'sigma_meteo_saisi_pct'

#: Le libellé français de ce réglage, celui que le refus cite à l'écran.
LIBELLE_SIGMA_METEO_SAISI = 'Variabilité interannuelle saisie (σ météo)'


class IncertitudeInvalide(ValueError):
    """Une composante d'incertitude refusée, en NOMMANT le champ fautif.

    Règle fondateur du 08/09/2026 : une erreur désigne le champ, jamais un
    « non enregistré » générique.
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


def _pertes_neutralisees():
    """Les postes du moteur de ventes, TOUS À ZÉRO.

    La production qu'on lui donne porte DÉJÀ ses postes (CAL139/CAL238). La
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
        ``(None, 'absente', n)`` : un écart-type sur une seule valeur n'a
        pas de sens, et en fabriquer un serait un chiffre inventé.
    """
    valeurs = [float(v) for v in (totaux_par_annee or {}).values()
               if v is not None and float(v) > 0]
    if len(valeurs) < 2:
        return None, ORIGINE_ABSENTE, len(valeurs)
    moyenne = sum(valeurs) / len(valeurs)
    if moyenne <= 0:
        return None, ORIGINE_ABSENTE, len(valeurs)
    return (statistics.stdev(valeurs) / moyenne, ORIGINE_MESUREE,
            len(valeurs))


def _sigma_meteo_saisi(reglages):
    """σ météo SAISI par la société, ou ``(None, '')`` s'il ne l'est pas.

    Args:
        reglages: la section ``simulation`` des réglages société (CALX145),
            ``{clé: {valeur, source, reference}}``. Absente ⇒ rien de saisi,
            c'est-à-dire le comportement d'aujourd'hui (D-CALX 12).

    Returns:
        ``(sigma_relatif, reference)`` — ``sigma_relatif`` est SANS unité
        (le réglage, lui, est en %).

    Raises:
        IncertitudeInvalide: la valeur est là mais sans provenance, ou
            illisible. Elle est refusée en NOMMANT le champ, jamais ignorée
            en silence : un σ qu'on ne peut pas sourcer ne se défend pas.
    """
    brut = (reglages or {}).get(CLE_SIGMA_METEO_SAISI)
    if brut is None:
        return None, ''
    if not isinstance(brut, dict):
        raise IncertitudeInvalide(
            f'« {LIBELLE_SIGMA_METEO_SAISI} » doit être saisi avec sa '
            'provenance : {"valeur": …, "source": …, "reference": "…"}.',
            champ=CLE_SIGMA_METEO_SAISI)
    if not str(brut.get('source') or '').strip():
        raise IncertitudeInvalide(
            f'« {LIBELLE_SIGMA_METEO_SAISI} » n\'a aucune source : cet '
            "écart-type est refusé et n'entre pas dans le calcul de σ. "
            'Renseignez sa provenance (réglage de la société ou publication '
            'citée), ou retirez la valeur.',
            champ=CLE_SIGMA_METEO_SAISI)
    try:
        pourcent = float(brut.get('valeur'))
    except (TypeError, ValueError):
        raise IncertitudeInvalide(
            f'« {LIBELLE_SIGMA_METEO_SAISI} » doit porter un nombre en % '
            f"(reçu : {brut.get('valeur')!r}).",
            champ=CLE_SIGMA_METEO_SAISI)
    if pourcent < 0:
        raise IncertitudeInvalide(
            f'« {LIBELLE_SIGMA_METEO_SAISI} » ne peut pas être négatif : un '
            'écart-type est une dispersion, jamais un retrait.',
            champ=CLE_SIGMA_METEO_SAISI)
    return pourcent / 100.0, str(brut.get('reference') or '').strip()


def _rendement_specifique(base, kwc):
    """kWh/kWc — le seul chiffre qui reste servi quand σ est refusé."""
    try:
        puissance = float(kwc) if kwc is not None else None
    except (TypeError, ValueError):
        return None
    if puissance is None or puissance <= 0:
        return None
    return round(base / puissance, 1)


def _motif_de_refus(annees):
    """Le texte français qui REMPLACE le repli supprimé par CALX184."""
    if annees > 1:
        observees = f'{annees} années observées ne dispersent rien de mesurable'
    elif annees == 1:
        observees = 'la fenêtre météo ne porte qu\'une seule année'
    else:
        observees = 'aucune année de production n\'a été observée'
    return (
        f'σ n\'a pas pu être établi : {observees}, et aucune variabilité '
        "n'a été saisie pour cette société. P75, P90 et P95 restent « non "
        'calculés » — aucune valeur de référence n\'est appliquée à leur '
        f'place. Renseignez « {LIBELLE_SIGMA_METEO_SAISI} » dans les '
        'réglages de simulation, avec sa source.')


def bankable(p50_kwh, *, totaux_par_annee=None, kwc=None, reglages=None):
    """P50 / P75 / P90 d'une production déjà nette de ses postes de CAL139.

    Args:
        p50_kwh: la production annuelle du calepinage (déjà amputée des
            postes de CAL139, puisqu'ils sont partis dans la requête PVGIS).
        totaux_par_annee: ``{annee: kWh}`` pour MESURER σ. Moins de deux
            années ⇒ on se rabat sur le σ saisi, ou on refuse.
        kwc: la puissance crête, pour le rendement spécifique.
        reglages: la section ``simulation`` des réglages société (CALX145),
            d'où vient le σ SAISI quand il n'est pas mesurable.

    Returns:
        dict — ``p50_kwh``, ``p75_kwh``, ``p90_kwh``,
        ``annual_variability`` (σ employé), ``sigma_source``
        (``mesuree``/``saisie``/``absente``), ``sigma_annees``,
        ``sigma_reference``, ``specific_yield_kwh_kwc``, ``commentaire``.
        ``p50_kwh`` absent ou ≤ 0 ⇒ toutes les sorties valent ``None`` (jamais
        des zéros, qui se liraient « la toiture ne produit rien »). σ ni
        mesuré ni saisi ⇒ P75 et P90 valent ``None`` et le commentaire dit
        quoi renseigner.

    Raises:
        IncertitudeInvalide: un σ saisi sans provenance, refusé en nommant le
            champ.
    """
    try:
        base = float(p50_kwh) if p50_kwh is not None else None
    except (TypeError, ValueError):
        base = None
    if base is None or base <= 0:
        return {
            'p50_kwh': None, 'p75_kwh': None, 'p90_kwh': None,
            'annual_variability': None, 'sigma_source': None,
            'sigma_annees': 0, 'sigma_reference': '',
            'specific_yield_kwh_kwc': None,
            'commentaire': (
                "Aucune production n'a été simulée : P50, P75 et P90 restent "
                '« non calculés », jamais 0.'),
        }

    sigma, origine, annees = variabilite_interannuelle(totaux_par_annee)
    if sigma is not None:
        reference = f'seriescalc, {annees} années observées'
        commentaire = (
            'σ MESURÉ sur les productions annuelles réellement observées '
            f'({annees} années de la fenêtre PVGIS) : '
            f'{round(sigma * 100, 2)} %.')
    else:
        sigma, reference = _sigma_meteo_saisi(reglages)
        if sigma is None:
            origine = ORIGINE_ABSENTE
            return {
                'p50_kwh': round(base, 1),
                'p75_kwh': None, 'p90_kwh': None,
                'annual_variability': None, 'sigma_source': origine,
                'sigma_annees': None, 'sigma_reference': '',
                'specific_yield_kwh_kwc': _rendement_specifique(base, kwc),
                'commentaire': _motif_de_refus(annees),
            }
        origine = ORIGINE_SAISIE
        commentaire = (
            f'σ SAISI par la société ({round(sigma * 100, 2)} %) et sourcé : '
            f'{reference or "réglage de simulation"}. Aucune année de la '
            "fenêtre ne permettait de le mesurer.")

    resultat = simulate_bankable_yield(
        base,
        # Les postes de CAL139 sont DÉJÀ dans ``base`` (CAL238) : on neutralise
        # ceux du moteur de ventes pour ne pas les compter deux fois.
        loss_factors=_pertes_neutralisees(),
        annual_variability=sigma, kwc=kwc, include_p75=True)
    return {
        'p50_kwh': resultat['p50_kwh'],
        'p75_kwh': resultat['p75_kwh'],
        'p90_kwh': resultat['p90_kwh'],
        'annual_variability': resultat['annual_variability'],
        'sigma_source': origine,
        'sigma_annees': annees if origine == ORIGINE_MESUREE else None,
        'sigma_reference': reference,
        'specific_yield_kwh_kwc': resultat['specific_yield_kwh_kwc'],
        'commentaire': commentaire,
    }
