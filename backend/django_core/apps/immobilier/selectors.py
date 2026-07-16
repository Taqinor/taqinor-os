"""Sélecteurs LECTURE SEULE du module Immobilier.

Toute lecture vers un autre domaine (``ventes``/``installations``) passe
exclusivement par ses ``selectors.py`` (imports FONCTION-LOCAL, jamais
``apps.ventes.models``/``apps.installations.models`` importés en tête de
module) — frontière cross-app de CLAUDE.md.
"""


def echeances_impayees(company, today=None):
    """NTPRO8 — Échéances ``emise`` dont la facture ventes liée est en retard.

    Statut de règlement lu EXCLUSIVEMENT via ``apps.ventes.selectors``
    (``jours_impaye_facture``/``get_facture_scoped``, jamais un import de
    ``apps.ventes.models`` ni un modèle ``Paiement`` dupliqué ici). Renvoie
    une liste de dicts triée par jours de retard décroissant (les plus
    urgents d'abord) : ``{echeance_id, bail_id, locataire, local,
    periode_debut, montant_total, jours_retard, facture_ventes_id,
    facture_reference}``."""
    from apps.ventes.selectors import get_facture_scoped, jours_impaye_facture

    from .models import EcheanceLoyer

    qs = (
        EcheanceLoyer.objects
        .filter(company=company, statut__in=[
            EcheanceLoyer.Statut.EMISE, EcheanceLoyer.Statut.RELANCEE,
        ])
        .exclude(facture_ventes_id__isnull=True)
        .select_related('bail', 'bail__locataire', 'bail__local')
    )

    resultats = []
    for echeance in qs:
        jours = jours_impaye_facture(echeance.facture_ventes_id, company)
        if jours <= 0:
            continue
        facture = get_facture_scoped(company, echeance.facture_ventes_id)
        resultats.append({
            'echeance_id': echeance.id,
            'bail_id': echeance.bail_id,
            'locataire': echeance.bail.locataire.nom,
            'local': str(echeance.bail.local),
            'periode_debut': echeance.periode_debut,
            'montant_total': echeance.montant_total,
            'jours_retard': jours,
            'facture_ventes_id': echeance.facture_ventes_id,
            'facture_reference': getattr(facture, 'reference', None),
        })

    resultats.sort(key=lambda r: r['jours_retard'], reverse=True)
    return resultats
