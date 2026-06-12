from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.ventes.models import Facture, LigneFacture, Devis
from apps.stock.models import Produit
from apps.crm.models import Client
from authentication.permissions import IsResponsableOrAdmin


def _co(user):
    """Return company filter kwargs or None for superuser."""
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def dashboard(request):
    """
    Retourne tous les agregats pour la page Reporting en un seul appel.
    Toutes les donnees sont filtrees par company de l'utilisateur connecte.
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Acces refuse.'}, status=403)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    factures_qs = Facture.objects.filter(**co)

    ca_paye = factures_qs.filter(
        statut=Facture.Statut.PAYEE
    ).aggregate(total=Sum('lignes__prix_unitaire'))['total'] or Decimal('0')

    # CA payé calculé proprement via les lignes
    ca_paye = _ca_factures(factures_qs.filter(statut=Facture.Statut.PAYEE))

    # Factures en attente (émises + en retard)
    ca_attente = _ca_factures(
        factures_qs.filter(statut__in=[Facture.Statut.EMISE, Facture.Statut.EN_RETARD])
    )

    nb_clients = Client.objects.filter(**co).count()

    # Valeur stock = quantite * prix_vente
    produits = Produit.objects.filter(**co, is_archived=False)
    valeur_stock_dh = sum(
        (p.quantite_stock or 0) * p.prix_vente for p in produits
    )

    # ── CA mensuel (12 derniers mois) ─────────────────────────────────────────
    debut = date.today().replace(day=1) - timedelta(days=365)
    # Calcule le CA HT par mois via les lignes
    ca_mensuel = _ca_mensuel(
        factures_qs.filter(statut=Facture.Statut.PAYEE, date_emission__gte=debut)
    )

    # ── Top 5 produits vendus ─────────────────────────────────────────────────
    top_produits = (
        LigneFacture.objects
        .filter(facture__in=factures_qs.filter(statut=Facture.Statut.PAYEE))
        .values('produit__nom')
        .annotate(qte=Sum('quantite'))
        .order_by('-qte')[:5]
    )

    # ── Statuts des factures ──────────────────────────────────────────────────
    statuts_factures = (
        factures_qs
        .values('statut')
        .annotate(nb=Count('id'))
        .order_by('statut')
    )
    statut_labels = {
        'brouillon': 'Brouillon',
        'emise': 'Émise',
        'payee': 'Payée',
        'en_retard': 'En retard',
        'annulee': 'Annulée',
    }
    statut_colors = {
        'brouillon': '#94a3b8',
        'emise': '#3b82f6',
        'payee': '#22c55e',
        'en_retard': '#ef4444',
        'annulee': '#f59e0b',
    }

    # ── Taux conversion Devis → Facture ───────────────────────────────────────
    devis_qs = Devis.objects.filter(**co)
    nb_devis_total = devis_qs.count()
    nb_devis_acceptes = devis_qs.filter(statut=Devis.Statut.ACCEPTE).count()
    nb_factures_emises = factures_qs.exclude(
        statut__in=[Facture.Statut.BROUILLON, Facture.Statut.ANNULEE]
    ).count()

    # ── Stock critique (produits sous seuil, seuil > 0) ───────────────────────
    from django.db.models import F
    stock_alerte_list = list(
        Produit.objects
        .filter(**co, is_archived=False)
        .exclude(seuil_alerte=0)
        .filter(quantite_stock__lte=F('seuil_alerte'))
        .order_by('quantite_stock')
        .values('nom', 'quantite_stock', 'seuil_alerte')[:15]
    )

    # ── Créances clients ──────────────────────────────────────────────────────
    today = date.today()
    factures_impayees = (
        factures_qs
        .filter(statut__in=[Facture.Statut.EMISE, Facture.Statut.EN_RETARD])
        .select_related('client')
        .prefetch_related('lignes')
    )
    creances = {}
    for f in factures_impayees:
        cid = f.client_id
        if cid not in creances:
            creances[cid] = {
                'client': str(f.client),
                'nb_factures': 0,
                'montant_total': Decimal('0'),
                'jours_retard_max': 0,
            }
        montant = sum(
            ligne.quantite * ligne.prix_unitaire * (1 - ligne.remise / 100)
            for ligne in f.lignes.all()
        )
        creances[cid]['nb_factures'] += 1
        creances[cid]['montant_total'] += montant
        if f.date_echeance:
            retard = (today - f.date_echeance).days
            if retard > creances[cid]['jours_retard_max']:
                creances[cid]['jours_retard_max'] = retard

    creances_list = sorted(
        [
            {**v, 'montant_total': float(v['montant_total'])}
            for v in creances.values()
        ],
        key=lambda x: x['montant_total'],
        reverse=True,
    )[:10]

    return Response({
        'kpis': {
            'ca_paye': float(ca_paye),
            'ca_attente': float(ca_attente),
            'nb_clients': nb_clients,
            'valeur_stock': float(valeur_stock_dh),
        },
        'ca_mensuel': ca_mensuel,
        'top_produits': [
            {'nom': t['produit__nom'], 'qte': float(t['qte'])}
            for t in top_produits
        ],
        'statuts_factures': [
            {
                'name': statut_labels.get(s['statut'], s['statut']),
                'value': s['nb'],
                'color': statut_colors.get(s['statut'], '#94a3b8'),
            }
            for s in statuts_factures
        ],
        'conversion': {
            'nb_devis': nb_devis_total,
            'nb_acceptes': nb_devis_acceptes,
            'nb_factures': nb_factures_emises,
        },
        'stock_alerte': stock_alerte_list,
        'creances': creances_list,
    })


def _ca_factures(qs):
    """Calcule le CA HT total d'un queryset de Facture."""
    total = Decimal('0')
    for f in qs.prefetch_related('lignes'):
        for ligne in f.lignes.all():
            total += ligne.quantite * ligne.prix_unitaire * (1 - ligne.remise / 100)
    return total


def _ca_mensuel(factures_qs):
    """
    Retourne le CA HT par mois pour les 12 derniers mois.
    Format : [{'mois': 'Jan 2025', 'ca': 12345.67}, ...]
    """
    from collections import defaultdict

    par_mois = defaultdict(Decimal)
    for f in factures_qs.prefetch_related('lignes'):
        cle = f.date_emission.strftime('%Y-%m')
        for ligne in f.lignes.all():
            par_mois[cle] += ligne.quantite * ligne.prix_unitaire * (1 - ligne.remise / 100)

    mois_labels = {
        '01': 'Jan', '02': 'Fév', '03': 'Mar', '04': 'Avr',
        '05': 'Mai', '06': 'Jun', '07': 'Jul', '08': 'Aoû',
        '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Déc',
    }

    result = []
    today = date.today()
    for i in range(11, -1, -1):
        d = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        cle = d.strftime('%Y-%m')
        mois_num = d.strftime('%m')
        label = f"{mois_labels[mois_num]} {d.year}"
        result.append({'mois': label, 'ca': float(par_mois.get(cle, 0))})

    return result
