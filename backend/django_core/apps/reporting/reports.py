"""T13/T14/T15 — Hub « Rapports » (lecture seule, multi-tenant).

Trois rapports agrégés à la lecture : ventes/pipeline (T13), stock (T14),
service chantier+SAV (T15). Chacun renvoie du JSON ; avec ?format=xlsx il
renvoie un .xlsx (table principale). Le PRIX D'ACHAT (stock) est interne :
présent dans le rapport stock (usage interne), jamais dans un export client.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum, F, DecimalField
from django.db.models.functions import Coalesce
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from apps.crm.exports import build_xlsx_response
from apps.crm import stages as stage_mod


def _co(user):
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


def _maybe_xlsx(request, filename, headers, rows, title):
    # NB: on n'utilise PAS le paramètre `format` (réservé par DRF pour la
    # négociation de contenu) — d'où `export=xlsx`.
    if request.query_params.get('export') == 'xlsx':
        return build_xlsx_response(filename, headers, rows, sheet_title=title)
    return None


def _qdate(value):
    """Parse une date ?from=/?to= au format ISO (AAAA-MM-JJ), ou None."""
    try:
        return date.fromisoformat((value or '').strip())
    except (ValueError, TypeError):
        return None


def _period(request):
    """Fenêtre de période depuis ?from=&to= (chacune optionnelle)."""
    return (_qdate(request.query_params.get('from')),
            _qdate(request.query_params.get('to')))


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def sales_report(request):
    """T13 — ventes/pipeline : funnel par étape, par responsable, par canal,
    par mois, gains/pertes par motif."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    from apps.crm.models import Lead
    from apps.ventes.models import Devis
    from apps.ventes.utils.expiry import is_expired

    start, end = _period(request)
    leads = Lead.objects.filter(**co, is_archived=False)
    if start:
        leads = leads.filter(date_creation__date__gte=start)
    if end:
        leads = leads.filter(date_creation__date__lte=end)

    funnel = []
    total = leads.count()
    for key in stage_mod.STAGES:
        n = leads.filter(stage=key).count()
        funnel.append({'stage': key, 'label': stage_mod.STAGE_LABELS.get(key, key),
                       'count': n})
    par_responsable = list(
        leads.values('owner__username')
        .annotate(count=Count('id'),
                  gagnes=Count('id', filter=models_q_signed()))
        .order_by('-count'))
    par_canal = list(
        leads.values('canal').annotate(count=Count('id')).order_by('-count'))
    perdus = list(
        leads.filter(perdu=True).values('motif_perte')
        .annotate(count=Count('id')).order_by('-count'))

    # ── Devis par statut (expiration à la volée) — un bucket « Expiré »
    #    apparaît pour les devis en attente dont la validité est dépassée. ──
    devis_qs = Devis.objects.filter(**co)
    if start:
        devis_qs = devis_qs.filter(date_creation__date__gte=start)
    if end:
        devis_qs = devis_qs.filter(date_creation__date__lte=end)
    statut_labels = dict(Devis.Statut.choices)
    statut_labels['expire'] = 'Expiré'
    devis_buckets = {}
    for d in devis_qs:
        statut = 'expire' if is_expired(d) else d.statut
        devis_buckets[statut] = devis_buckets.get(statut, 0) + 1
    devis_par_statut = [
        {'statut': k, 'label': statut_labels.get(k, k), 'count': v}
        for k, v in sorted(devis_buckets.items(), key=lambda kv: -kv[1])
    ]

    rows = [[f['label'], f['count']] for f in funnel]
    x = _maybe_xlsx(request, 'rapport-ventes.xlsx',
                    ['Étape', 'Leads'], rows, 'Ventes')
    if x:
        return x
    return Response({
        'funnel': funnel, 'total_leads': total,
        'par_responsable': par_responsable, 'par_canal': par_canal,
        'perdus_par_motif': perdus,
        'devis_par_statut': devis_par_statut,
    })


def models_q_signed():
    from django.db.models import Q
    return Q(stage='SIGNED')


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def stock_report(request):
    """T14 — stock : valorisation (vente + achat interne), bas stock, par
    catégorie. Le prix d'achat reste un repère INTERNE."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    from apps.stock.models import Produit
    qs = Produit.objects.filter(**co, is_archived=False)

    dec = DecimalField()
    sum_vente = Coalesce(
        Sum(F('prix_vente') * F('quantite_stock'), output_field=dec),
        Decimal('0'))
    sum_achat = Coalesce(
        Sum(F('prix_achat') * F('quantite_stock'), output_field=dec),
        Decimal('0'))
    val_vente = qs.aggregate(t=sum_vente)['t']
    val_achat = qs.aggregate(t=sum_achat)['t']
    par_categorie = list(
        qs.values('categorie__nom')
        .annotate(nb=Count('id'), valeur_vente=sum_vente)
        .order_by('-valeur_vente'))
    # ERR57 — `seuil_alerte=0` signifie « aucun seuil » : exclu de la liste bas
    # stock (cohérent avec le dashboard), sinon tout produit à 0 en stock par
    # défaut serait faussement signalé.
    bas_stock = list(
        qs.exclude(seuil_alerte=0)
        .filter(quantite_stock__lte=F('seuil_alerte'))
        .values('nom', 'sku', 'quantite_stock', 'seuil_alerte')[:200])

    rows = [[c['categorie__nom'] or '—', c['nb'], str(c['valeur_vente'])]
            for c in par_categorie]
    x = _maybe_xlsx(request, 'rapport-stock.xlsx',
                    ['Catégorie', 'Articles', 'Valeur vente HT'], rows, 'Stock')
    if x:
        return x
    return Response({
        'valorisation_vente': str(val_vente),
        'valorisation_achat': str(val_achat),  # interne, non client-facing
        'par_categorie': [
            {**c, 'valeur_vente': str(c['valeur_vente'])} for c in par_categorie],
        'bas_stock': bas_stock,
    })


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def service_report(request):
    """T15 — service : chantiers par statut, activité technicien, SAV ouverts
    vs résolus, garanties expirant ≤90 j."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    from apps.installations.models import Installation, Intervention
    from apps.sav.models import Equipement, Ticket

    start, end = _period(request)
    inst_qs = Installation.objects.filter(**co)
    interv_qs = Intervention.objects.filter(**co)
    ticket_qs = Ticket.objects.filter(**co)
    if start:
        inst_qs = inst_qs.filter(date_creation__date__gte=start)
        interv_qs = interv_qs.filter(date_prevue__gte=start)
        ticket_qs = ticket_qs.filter(date_creation__date__gte=start)
    if end:
        inst_qs = inst_qs.filter(date_creation__date__lte=end)
        interv_qs = interv_qs.filter(date_prevue__lte=end)
        ticket_qs = ticket_qs.filter(date_creation__date__lte=end)

    chantiers_statut = list(
        inst_qs.values('statut')
        .annotate(count=Count('id')).order_by('-count'))
    interventions_tech = list(
        interv_qs.values('technicien__username')
        .annotate(count=Count('id')).order_by('-count'))
    tickets_statut = list(
        ticket_qs.values('statut')
        .annotate(count=Count('id')).order_by('-count'))
    open_statuts = list(Ticket.OPEN_STATUTS)
    tickets_ouverts = ticket_qs.filter(statut__in=open_statuts).count()
    tickets_resolus = ticket_qs.exclude(
        statut__in=open_statuts).count()
    horizon = date.today() + timedelta(days=90)
    garanties = Equipement.objects.filter(
        **co, date_fin_garantie__gte=date.today(),
        date_fin_garantie__lte=horizon).count()

    rows = [[c['statut'], c['count']] for c in chantiers_statut]
    x = _maybe_xlsx(request, 'rapport-service.xlsx',
                    ['Statut chantier', 'Nombre'], rows, 'Service')
    if x:
        return x
    return Response({
        'chantiers_par_statut': chantiers_statut,
        'interventions_par_technicien': interventions_tech,
        'tickets_par_statut': tickets_statut,
        'tickets_ouverts': tickets_ouverts,
        'tickets_resolus': tickets_resolus,
        'garanties_expirantes_90j': garanties,
    })
