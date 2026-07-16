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


def _travaux_pour_locaux(company, locaux_ids):
    """NTPRO9 — Coût des travaux (chantiers) liés aux locaux d'un site/bâtiment.

    Lu via ``apps.installations.selectors`` (function-local, jamais un import
    de ``apps.installations.models``) — AUCUN champ de lien persistant
    Local↔chantier n'existe encore dans ce lot (une future tâche l'ajoutera) :
    dégrade donc TOUJOURS proprement à 0 pour l'instant, jamais de crash ni
    d'exception qui remonterait à l'appelant."""
    from decimal import Decimal

    try:
        import apps.installations.selectors  # noqa: F401 — vérifie juste la présence du module
    except Exception:
        return Decimal('0')
    # Aucun mécanisme de résolution local→chantier n'est encore câblé
    # (pas de champ string-FK persistant sur Local à ce stade) : dégradation
    # propre attendue par NTPRO9 (« marge = revenus - charges » sans travaux).
    return Decimal('0')


def rentabilite_actif(company, *, site_id=None, batiment_id=None, periode=None):
    """NTPRO9 — Rentabilité par actif (site ou bâtiment) : loyers vs charges
    vs travaux.

    Agrège les revenus (Σ ``EcheanceLoyer`` émises/relancées/payées),
    les charges locatives réelles (NTPRO12, pas encore construit dans ce
    lot — dégrade à 0) et les travaux (``apps.installations.selectors``,
    dégrade à 0 tant qu'aucun chantier n'est lié) → marge nette + taux
    d'occupation. Fournit exactement un de ``site_id``/``batiment_id``.
    Ne remonte jamais aucun prix d'achat produit (rule CLAUDE.md)."""
    from decimal import Decimal

    from .models import EcheanceLoyer, Local

    if not site_id and not batiment_id:
        raise ValueError('rentabilite_actif requiert site_id ou batiment_id.')

    locaux = Local.objects.filter(company=company).select_related(
        'niveau', 'niveau__batiment')
    if batiment_id:
        locaux = locaux.filter(niveau__batiment_id=batiment_id)
    else:
        locaux = locaux.filter(niveau__batiment__site_id=site_id)

    locaux = list(locaux)
    total_locaux = len(locaux)
    locaux_loues = sum(1 for local in locaux if local.statut == Local.Statut.LOUE)
    taux_occupation = (
        Decimal(locaux_loues) / Decimal(total_locaux) * 100
        if total_locaux else Decimal('0')
    )

    echeances = (
        EcheanceLoyer.objects
        .filter(
            company=company,
            bail__local_id__in=[local.id for local in locaux],
            statut__in=[
                EcheanceLoyer.Statut.EMISE, EcheanceLoyer.Statut.PAYEE,
                EcheanceLoyer.Statut.RELANCEE,
            ],
        )
        .select_related('bail', 'bail__local')
    )
    if periode:
        echeances = echeances.filter(periode_debut__startswith=periode)

    revenus_par_local = {}
    revenus = Decimal('0')
    for echeance in echeances:
        revenus += echeance.montant_total
        local_id = echeance.bail.local_id
        revenus_par_local[local_id] = (
            revenus_par_local.get(local_id, Decimal('0'))
            + echeance.montant_total
        )

    # NTPRO12 (répartition des charges locatives réelles par local) n'est
    # PAS construit dans ce lot : dégrade à 0, jamais d'exception.
    charges = Decimal('0')
    travaux = _travaux_pour_locaux(company, [local.id for local in locaux])
    marge_nette = revenus - charges - travaux

    par_local = [
        {
            'local_id': local.id,
            'reference': local.reference,
            'statut': local.statut,
            'revenus': revenus_par_local.get(local.id, Decimal('0')),
        }
        for local in locaux
    ]

    return {
        'total_locaux': total_locaux,
        'locaux_loues': locaux_loues,
        'taux_occupation': taux_occupation,
        'revenus': revenus,
        'charges': charges,
        'travaux': travaux,
        'marge_nette': marge_nette,
        'par_local': par_local,
    }
