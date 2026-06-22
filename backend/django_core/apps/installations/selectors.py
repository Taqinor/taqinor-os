"""Sélecteurs LECTURE SEULE du domaine Installations exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les chantiers / interventions /
réservations de stock à travers ces fonctions plutôt qu'en important
`apps.installations.models` directement (voir CLAUDE.md, règle de modularité).
Comportement strictement identique aux requêtes inline d'origine.
"""
from django.db.models import Sum


def installation_for_devis(devis):
    """Le chantier lié à un devis (ou None). Lecture seule."""
    from .models import Installation
    return Installation.objects.filter(devis=devis).first()


def installation_summaries_for_devis(devis_qs):
    """Map {devis_id: {id, reference, statut}} des chantiers liés à un lot de
    devis — une seule requête (évite un N+1 sur la fiche lead)."""
    from .models import Installation
    return {
        i.devis_id: {'id': i.id, 'reference': i.reference, 'statut': i.statut}
        for i in Installation.objects.filter(devis__in=devis_qs)
    }


def installation_scoped(company, pk):
    """Chantier (Installation) scopé société, par id, avec client préchargé."""
    from .models import Installation
    return (Installation.objects
            .filter(company=company, id=pk)
            .select_related('client')
            .first())


def installation_qs_for_remise():
    """Queryset Installation prêt pour la fiche de remise (relations préchargées).
    L'appelant applique son propre scope société puis filtre par pk."""
    from .models import Installation
    return (Installation.objects
            .select_related('client', 'devis', 'company',
                            'technicien_responsable')
            .prefetch_related('devis__lignes__produit'))


def intervention_scoped(company, pk):
    """Intervention scopée société, par id, avec chantier + client préchargés."""
    from .models import Intervention
    return (Intervention.objects
            .filter(company=company, id=pk)
            .select_related('installation', 'installation__client')
            .first())


def reserved_quantity_for_produit(produit):
    """Quantité d'un produit ENGAGÉE par des réservations de chantier actives et
    non encore consommées (0 si aucune). Lecture seule."""
    agg = (_active_reservations()
           .filter(produit=produit)
           .aggregate(total=Sum('quantite')))
    return agg['total'] or 0


def reserved_quantities_for_company(company):
    """Map {produit_id: quantité réservée active} pour toute la société — un seul
    agrégat (évite un N+1 sur la liste produits). Lecture seule."""
    rows = (_active_reservations()
            .filter(company=company)
            .values('produit_id')
            .annotate(total=Sum('quantite')))
    return {r['produit_id']: (r['total'] or 0) for r in rows}


def own_reservation_map(installation):
    """Map {produit_id: quantité} des réservations actives non consommées propres
    à CE chantier (pour ne pas les décompter de son propre disponible)."""
    rows = (_active_reservations()
            .filter(installation=installation)
            .values_list('produit_id', 'quantite'))
    return {pid: qte for pid, qte in rows}


def update_installation_lead(absorbed_lead, survivor_lead):
    """Réassigne les chantiers liés au lead absorbé vers le lead survivant (fusion
    de leads). Renvoie le nombre de chantiers réassignés."""
    from .models import Installation
    return Installation.objects.filter(lead=absorbed_lead).update(
        lead=survivor_lead)


def _active_reservations():
    from .models import StockReservation
    return StockReservation.objects.filter(active=True, consomme=False)


def reserve_scoped(company, pk):
    """Réserve (F16 — point de finition) scopée société, par id, ou ``None``.

    Point d'entrée cross-app LECTURE SEULE : les autres apps (ex. QHSE, pour le
    pont Réserve → NCR) lisent une ``Reserve`` à travers ce sélecteur plutôt
    qu'en important ``installations.models`` directement. Scopé société :
    ``None`` si la réserve n'appartient pas à ``company``."""
    from .models import Reserve
    return (Reserve.objects
            .filter(company=company, pk=pk)
            .select_related('intervention', 'intervention__installation')
            .first())


def reserve_resume(reserve):
    """Résumé LECTURE SEULE d'une ``Reserve`` pour un pont cross-app (→ NCR).

    Renvoie un dict plat ``{id, description, statut, intervention_id,
    chantier_id}`` — jamais l'instance du modèle — pour qu'une autre app
    construise une fiche (ex. non-conformité QHSE) sans importer le modèle ni
    coupler les apps. ``chantier_id`` est l'id du chantier (Installation) de
    l'intervention, ``None`` s'il n'y en a pas."""
    intervention = getattr(reserve, 'intervention', None)
    chantier_id = getattr(intervention, 'installation_id', None)
    return {
        'id': reserve.id,
        'description': reserve.description or '',
        'statut': reserve.statut,
        'intervention_id': reserve.intervention_id,
        'chantier_id': chantier_id,
    }


def chantier_card(chantier_id, company):
    """S8 — fiche-carte LECTURE SEULE d'un chantier (Installation) pour le
    partage dans la messagerie. Scopée société : None si le chantier n'appartient
    pas à la société. Format {label, subtitle, url}."""
    from .models import Installation
    chantier = (Installation.objects.filter(pk=chantier_id, company=company)
                .select_related('client').first())
    if chantier is None:
        return None
    parts = []
    try:
        parts.append(chantier.get_statut_display())
    except Exception:  # pragma: no cover - défensif
        pass
    client = getattr(chantier, 'client', None)
    if client is not None:
        parts.append(str(client))
    if getattr(chantier, 'site_ville', None):
        parts.append(chantier.site_ville)
    return {
        'label': f'Chantier {chantier.reference}',
        'subtitle': ' · '.join(p for p in parts if p),
        'url': f'/installations/{chantier.pk}',
    }
