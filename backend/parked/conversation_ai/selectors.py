"""Sélecteurs (LECTURE) du module « conversation_ai » (Groupe NTAI).

Point d'entrée UNIQUE des lectures cross-app : une autre app qui a besoin des
appels commerciaux appelle ces fonctions, jamais les modèles de ce module.
Toute lecture est SCOPÉE SOCIÉTÉ — aucune fonction n'expose une requête non
filtrée.
"""
from __future__ import annotations


def appels_for_company(company):
    """Tous les appels commerciaux d'une société (queryset scopé)."""
    from .models import AppelCommercial

    return AppelCommercial.objects.filter(company=company)


def appels_for_lead(company, lead_id):
    """Appels rattachés à un lead donné, scopés société."""
    return appels_for_company(company).filter(lead_id=lead_id)


def appels_transcrits(company):
    """Appels dont la transcription a abouti (base des analyses)."""
    from .models import AppelCommercial

    return appels_for_company(company).filter(
        statut=AppelCommercial.STATUT_TRANSCRIT)


_SENTIMENTS_CONNUS = ('positif', 'neutre', 'negatif')


def synthese_appels(company, periode=None):
    """NTAI23 — Coaching commercial agrégé sur les appels ANALYSÉS (NTAI22).

    Agrège, LECTURE SEULE et SCOPÉ SOCIÉTÉ, les ``analyse_json`` des appels
    dont l'analyse a déjà eu lieu (``analyse_le`` renseigné — un appel non
    analysé n'a rien à agréger) : objections les plus fréquentes, sentiment
    moyen, produits cités et un découpage PAR COMMERCIAL.

    ``periode`` : ``(debut, fin)`` (dates, bornes incluses, l'une ou l'autre
    optionnelle) appliqué sur ``analyse_le`` ; ``None`` = tout l'historique.

    Le « commercial » d'un appel est le ``owner`` du LEAD rattaché (résolu via
    ``apps.crm.selectors.get_company_lead`` — jamais un import direct de
    ``crm.models``) : un appel sans lead, ou dont le lead n'a pas de owner,
    n'entre dans AUCUN groupe « par_commercial » (jamais une attribution
    devinée).
    """
    from .models import AppelCommercial

    qs = AppelCommercial.objects.filter(
        company=company, analyse_le__isnull=False)
    if periode:
        debut, fin = periode
        if debut is not None:
            qs = qs.filter(analyse_le__date__gte=debut)
        if fin is not None:
            qs = qs.filter(analyse_le__date__lte=fin)

    appels = list(qs)
    objections_count = {}
    produits_count = {}
    sentiment_count = {cle: 0 for cle in _SENTIMENTS_CONNUS}
    par_commercial = {}
    lead_owner_cache = {}

    for appel in appels:
        analyse = appel.analyse_json or {}
        for objection in analyse.get('objections') or []:
            objection = str(objection).strip()
            if objection:
                objections_count[objection] = (
                    objections_count.get(objection, 0) + 1)
        for produit in analyse.get('produits') or []:
            produit = str(produit).strip()
            if produit:
                produits_count[produit] = produits_count.get(produit, 0) + 1

        sentiment = appel.sentiment or 'neutre'
        if sentiment in sentiment_count:
            sentiment_count[sentiment] += 1

        if not appel.lead_id:
            continue
        if appel.lead_id not in lead_owner_cache:
            from apps.crm.selectors import get_company_lead
            lead = get_company_lead(company, appel.lead_id)
            owner_nom = (
                getattr(lead.owner, 'username', None)
                if lead is not None and lead.owner_id else None)
            lead_owner_cache[appel.lead_id] = owner_nom
        owner_nom = lead_owner_cache[appel.lead_id]
        if not owner_nom:
            continue
        slot = par_commercial.setdefault(owner_nom, {
            'commercial': owner_nom, 'nb_appels': 0, 'positifs': 0,
        })
        slot['nb_appels'] += 1
        if sentiment == 'positif':
            slot['positifs'] += 1

    total_sentiment_connu = sum(sentiment_count.values())
    sentiment_moyen_global = (
        round(sentiment_count['positif'] / total_sentiment_connu, 2)
        if total_sentiment_connu else None)

    top_objections = sorted(
        ({'objection': cle, 'nb': nb}
         for cle, nb in objections_count.items()),
        key=lambda r: (-r['nb'], r['objection']))[:10]
    produits_cites = sorted(
        ({'produit': cle, 'nb': nb} for cle, nb in produits_count.items()),
        key=lambda r: (-r['nb'], r['produit']))[:10]
    par_commercial_out = sorted(
        ({'commercial': v['commercial'], 'nb_appels': v['nb_appels'],
          'sentiment_positif_pct': (
              round(100.0 * v['positifs'] / v['nb_appels'], 1)
              if v['nb_appels'] else 0.0)}
         for v in par_commercial.values()),
        key=lambda r: (-r['nb_appels'], r['commercial']))

    return {
        'nb_appels_analyses': len(appels),
        'top_objections': top_objections,
        'sentiment_moyen_global': sentiment_moyen_global,
        'produits_cites': produits_cites,
        'par_commercial': par_commercial_out,
    }
