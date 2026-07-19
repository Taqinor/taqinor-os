"""PUB95 — Détection de cannibalisation (les pubs créent-elles ou DÉPLACENT-elles ?).

« Ces pubs créent-elles des leads INCRÉMENTAUX ou déplacent-elles simplement
l'organique/le parrainage ? » On compare la TENDANCE des leads organiques +
parrainage AVANT vs APRÈS un changement de dépense publicitaire (série temporelle
simple — **PAS un géo-test**, qui est le rôle de l'incrementality géo-holdout).

Logique honnête (régime bas-volume §0) : les comptes de leads sont des comptages
de Poisson à un chiffre par semaine ; un point-estimate y serait mensonger. On
borne donc chaque taux quotidien par une CI de Poisson EXACTE (``mde.poisson_ci``,
réutilisée — jamais réimplémentée). Le verdict n'est rendu QUE si les intervalles
AVANT/APRÈS ne se chevauchent pas ; sinon, on dit clairement « données
insuffisantes pour conclure » — jamais un faux signal de cannibalisation.

Le cœur (:func:`compare_before_after`) est **pur** ; la couche modèle
(:func:`cannibalization_report`) lit la dépense (``InsightSnapshot``, in-app) et
les leads organiques/parrainage via ``crm.selectors.organic_referral_lead_series``
(jamais un import de ``apps.crm.models``).
"""
from __future__ import annotations

import datetime

from . import mde

# En deçà de ce total de leads organiques/parrainage (avant + après), aucune
# conclusion n'est fiable : on le dit clairement (jamais un faux verdict).
DEFAULT_MIN_LEADS = 10
DEFAULT_WINDOW_DAYS = 28   # 4 semaines de part et d'autre du changement
DEFAULT_CONFIDENCE = 0.95


def compare_before_after(pre_total, pre_days, post_total, post_days, *,
                         min_leads=DEFAULT_MIN_LEADS,
                         confidence=DEFAULT_CONFIDENCE):
    """Compare deux fenêtres de comptages de leads (organique+parrainage). Pure.

    ``pre_total``/``post_total`` : leads organiques+parrainage AVANT/APRÈS ;
    ``pre_days``/``post_days`` : longueurs des fenêtres (jours). Renvoie ::

        {'pre_rate', 'post_rate', 'pre_ci', 'post_ci', 'delta_rate',
         'verdict', 'insufficient_data'}

    Les taux sont QUOTIDIENS ; les CI viennent de la CI de Poisson exacte du
    comptage, divisée par le nombre de jours. Verdict (FR) :

      * ``insufficient_data`` — trop peu de leads OU fenêtre vide ;
      * ``cannibalisation`` — la CI APRÈS est ENTIÈREMENT sous la CI AVANT
        (l'organique a chuté quand la dépense a changé) ;
      * ``incremental`` — la CI APRÈS est ENTIÈREMENT au-dessus (l'organique a
        même monté : les pubs semblent créer des leads sans déplacer) ;
      * ``indetermine`` — les intervalles se chevauchent : pas de signal net.
    """
    if pre_days <= 0 or post_days <= 0 or (pre_total + post_total) < min_leads:
        return {
            'pre_rate': None, 'post_rate': None, 'pre_ci': None,
            'post_ci': None, 'delta_rate': None,
            'verdict': 'insufficient_data', 'insufficient_data': True}

    pre_low, pre_high = mde.poisson_ci(pre_total, confidence=confidence)
    post_low, post_high = mde.poisson_ci(post_total, confidence=confidence)
    # Ramener les CI de comptage en TAUX quotidiens (÷ nombre de jours).
    pre_ci = (pre_low / pre_days, pre_high / pre_days)
    post_ci = (post_low / post_days, post_high / post_days)
    pre_rate = pre_total / pre_days
    post_rate = post_total / post_days

    if post_ci[1] < pre_ci[0]:
        verdict = 'cannibalisation'
    elif post_ci[0] > pre_ci[1]:
        verdict = 'incremental'
    else:
        verdict = 'indetermine'

    return {
        'pre_rate': round(pre_rate, 4),
        'post_rate': round(post_rate, 4),
        'pre_ci': [round(pre_ci[0], 4), round(pre_ci[1], 4)],
        'post_ci': [round(post_ci[0], 4), round(post_ci[1], 4)],
        'delta_rate': round(post_rate - pre_rate, 4),
        'verdict': verdict,
        'insufficient_data': False,
    }


_VERDICT_FR = {
    'insufficient_data': ("Données insuffisantes : trop peu de leads organiques/"
                          "parrainage pour conclure sur une cannibalisation."),
    'cannibalisation': ("Risque de cannibalisation : les leads organiques/"
                        "parrainage ont NETTEMENT chuté après le changement de "
                        "dépense — les pubs déplacent peut-être l'organique plutôt "
                        "que d'ajouter des leads."),
    'incremental': ("Pas de cannibalisation détectée : les leads organiques/"
                    "parrainage n'ont pas chuté (voire ont monté) — les pubs "
                    "semblent créer des leads incrémentaux."),
    'indetermine': ("Pas de signal net : les intervalles avant/après se "
                    "chevauchent. Données insuffisantes pour trancher — surveiller "
                    "sur une fenêtre plus longue."),
}


def _sum_organic_referral(series, start, end):
    """Somme (organique + parrainage) sur ``[start, end]`` inclus. Pure-ish."""
    total = 0
    day = start
    while day <= end:
        slot = series.get(day.isoformat())
        if slot:
            total += slot.get('organic', 0) + slot.get('referral', 0)
        day += datetime.timedelta(days=1)
    return total


def cannibalization_report(company, *, change_date, now=None,
                           window_days=DEFAULT_WINDOW_DAYS,
                           min_leads=DEFAULT_MIN_LEADS):
    """PUB95 — Rapport FR de cannibalisation autour d'un ``change_date`` (date du
    changement de dépense). Society-scopé. Compare la tendance des leads
    organiques+parrainage sur ``window_days`` AVANT vs APRÈS. « Données
    insuffisantes → le dit » explicitement. Renvoie un dict JSON-sûr avec
    ``rapport_fr`` + les chiffres + l'intervalle honnête.
    """
    from apps.crm.selectors import organic_referral_lead_series

    pre_start = change_date - datetime.timedelta(days=window_days)
    pre_end = change_date - datetime.timedelta(days=1)
    post_start = change_date
    post_end = change_date + datetime.timedelta(days=window_days - 1)

    series = organic_referral_lead_series(
        company, date_start=pre_start, date_end=post_end)

    pre_total = _sum_organic_referral(series, pre_start, pre_end)
    post_total = _sum_organic_referral(series, post_start, post_end)
    pre_days = (pre_end - pre_start).days + 1
    post_days = (post_end - post_start).days + 1

    result = compare_before_after(
        pre_total, pre_days, post_total, post_days, min_leads=min_leads)
    result.update({
        'change_date': change_date.isoformat(),
        'window_days': window_days,
        'pre_total': pre_total,
        'post_total': post_total,
        'rapport_fr': _VERDICT_FR[result['verdict']],
    })
    return result
