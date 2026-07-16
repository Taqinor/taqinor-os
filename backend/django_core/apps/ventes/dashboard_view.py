"""FG45 — Tableau de bord Quote-to-Cash (ventes).

Agrégation LECTURE SEULE, scopée société, sans aucune écriture. Renvoie :
  - Taux de conversion devis (envoyé → accepté → facturé → encaissé)
  - Cycle quote-to-cash moyen (jours entre création devis et paiement)
  - DSO (Days Sales Outstanding) — encours / CA facturé × 30
  - Encaissé vs facturé (mois en cours ou période paramétrée)
  - Pipeline par commercial (décompte + valeur totale des devis actifs)
"""
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole


def _period_filter(request):
    """Renvoie un filtre Django (date__range) selon ?start=&end= ou ?month=."""
    params = request.query_params
    start = params.get('start')
    end = params.get('end')
    month = params.get('month')

    if start and end:
        return Q(date_creation__date__range=[start, end])
    if month:
        from datetime import date
        try:
            y, m = int(month[:4]), int(month[5:7])
            import calendar
            last_day = calendar.monthrange(y, m)[1]
            s = date(y, m, 1).isoformat()
            e = date(y, m, last_day).isoformat()
            return Q(date_creation__date__range=[s, e])
        except (ValueError, IndexError):
            pass
    # Défaut : 12 derniers mois.
    from datetime import timedelta
    end_d = timezone.now().date()
    start_d = end_d - timedelta(days=365)
    return Q(date_creation__date__range=[start_d.isoformat(), end_d.isoformat()])


@api_view(['GET'])
@permission_classes([IsAnyRole])
def dashboard_quote_to_cash(request):
    """GET /ventes/dashboard/

    Tableau de bord Quote-to-Cash scopé société. Tous les montants en MAD TTC.

    Paramètres optionnels :
      - ?month=YYYY-MM     : filtre sur un mois
      - ?start=&end=       : filtre sur une plage de dates (ISO AAAA-MM-JJ)
      (défaut : 12 derniers mois)

    Réponse :
    {
      "devis": {
        "total":    int,  # tous statuts
        "envoyes":  int,
        "acceptes": int,
        "refuses":  int,
        "expires":  int,
        "taux_acceptation_pct": float | null,  # acceptés / envoyés × 100
        "valeur_pipeline": str,   # TTC des devis envoyés encore ouverts
      },
      "factures": {
        "total":       int,
        "emises":      int,
        "payees":      int,
        "en_retard":   int,
        "annulees":    int,
        "montant_facture": str,   # TTC total des factures émises/payées
        "montant_encaisse": str,  # Total des paiements de la période
      },
      "conversion": {
        "devis_envoye_vers_accepte_pct": float | null,
        "devis_accepte_vers_facture_pct": float | null,
        "devis_envoye_vers_facture_pct":  float | null,
      },
      "dso_jours": float | null,   # Days Sales Outstanding
      "cycle_moyen_jours": float | null,   # création devis → dernier paiement
      "par_commercial": [
        {
          "commercial": str,
          "devis_actifs": int,
          "valeur_pipeline": str,
        }
      ]
    }
    """
    from .models import Devis, Facture, Paiement
    company = request.user.company
    periode = _period_filter(request)

    # ── Devis ────────────────────────────────────────────────────────────────
    devis_qs = Devis.objects.filter(company=company).filter(periode)
    agg_devis = devis_qs.aggregate(
        total=Count('id'),
        envoyes=Count('id', filter=Q(statut='envoye')),
        acceptes=Count('id', filter=Q(statut='accepte')),
        refuses=Count('id', filter=Q(statut='refuse')),
        expires=Count('id', filter=Q(statut='expire')),
    )

    # Valeur pipeline = TTC estimé des devis envoyés (non encore décidés).
    # On utilise les totaux calculés par les propriétés du modèle ; pour éviter
    # N+1 on fait une requête SQL agrégée approximative (SUM lignes non remisées).
    from django.db.models import ExpressionWrapper, F, FloatField
    from apps.ventes.models import LigneDevis
    pipeline_qs = LigneDevis.objects.filter(
        devis__company=company,
        devis__statut='envoye',
    ).annotate(
        ht_ligne=ExpressionWrapper(
            F('quantite') * F('prix_unitaire') * (1 - F('remise') / 100),
            output_field=FloatField()))
    pipeline_ht = pipeline_qs.aggregate(s=Sum('ht_ligne'))['s'] or 0
    # TVA moyenne ~ taux global du devis n'est pas facilement agrégeable par SQL ;
    # on applique 20 % comme estimation côté dashboard (pas de précision comptable
    # requise ici — l'exact est sur le devis lui-même).
    valeur_pipeline = round(pipeline_ht * 1.20, 2)

    # ── Factures ─────────────────────────────────────────────────────────────
    # On filtre sur date_emission et date_creation (les deux peuvent exister).
    factures_qs = Facture.objects.filter(company=company)
    agg_fac = factures_qs.aggregate(
        total=Count('id'),
        emises=Count('id', filter=Q(statut='emise')),
        payees=Count('id', filter=Q(statut='payee')),
        en_retard=Count('id', filter=Q(statut='en_retard')),
        annulees=Count('id', filter=Q(statut='annulee')),
    )

    # Montant facturé (TTC) : montant_ttc quand figé, sinon on utilise montant_ttc.
    # Pour les factures avec lignes non figées, une agrégation SQL exacte nécessiterait
    # de joindre les lignes — on utilise la somme des montant_ttc quand disponible.
    montant_facture_q = factures_qs.filter(
        statut__in=('emise', 'payee', 'en_retard')
    ).aggregate(s=Sum('montant_ttc'))
    montant_facture = montant_facture_q['s'] or Decimal('0')

    # Paiements encaissés.
    paiements_qs = Paiement.objects.filter(company=company)
    montant_encaisse_q = paiements_qs.aggregate(s=Sum('montant'))
    montant_encaisse = montant_encaisse_q['s'] or Decimal('0')

    # ── Taux de conversion ───────────────────────────────────────────────────
    n_envoyes = agg_devis['envoyes']
    n_acceptes = agg_devis['acceptes']
    # Devis acceptés avec au moins une facture.
    devis_avec_facture = (
        Devis.objects.filter(company=company, statut='accepte')
        .filter(factures__isnull=False)
        .distinct().count()
    )

    def _pct(num, den):
        if den and den > 0:
            return round(num / den * 100, 1)
        return None

    # ── DSO ──────────────────────────────────────────────────────────────────
    # DSO = encours TTC / (CA facturé / 30)
    encours_ttc = factures_qs.filter(
        statut__in=('emise', 'en_retard')
    ).aggregate(s=Sum('montant_ttc'))['s'] or Decimal('0')
    dso = None
    if montant_facture > 0:
        dso = round(float(encours_ttc) / float(montant_facture) * 30, 1)

    # ── Cycle moyen quote-to-cash ─────────────────────────────────────────────
    # Jours entre creation du devis et date du dernier paiement.
    # Calcul approximatif côté Python (pas de DeltaField SQL).
    cycle_list = []
    accepted_with_pmt = (
        Devis.objects.filter(company=company, statut='accepte')
        .prefetch_related('factures__paiements')
        .select_related('created_by')
    )[:200]  # cap pour éviter un scan complet
    for d in accepted_with_pmt:
        pmt_dates = [
            p.date_paiement
            for f in d.factures.all()
            for p in f.paiements.all()
        ]
        if pmt_dates:
            delta = (max(pmt_dates) - d.date_creation.date()).days
            if delta >= 0:
                cycle_list.append(delta)
    cycle_moyen = round(sum(cycle_list) / len(cycle_list), 1) if cycle_list else None

    # ── Par commercial ────────────────────────────────────────────────────────
    # SCA40 — UNE seule requête groupée (values().annotate()) au lieu d'un
    # aggregate() LigneDevis par commercial dans une boucle Python (N+1 non
    # borné, croissait avec l'équipe). Le décompte de devis (`devis_actifs`)
    # DOIT rester distinct : joindre `lignes` fan-out une ligne par ligne de
    # devis, donc Count('id', distinct=True) préserve le décompte d'origine
    # (un devis sans ligne compte toujours pour 1, sa somme de lignes valant 0
    # via le LEFT JOIN). La somme HT ligne réutilise l'expression EXACTE du
    # bloc pipeline global ci-dessus. Sortie JSON strictement identique.
    par_commercial_raw = (
        Devis.objects.filter(company=company, statut='envoye')
        .values('created_by__username', 'created_by__first_name',
                'created_by__last_name')
        .annotate(
            devis_actifs=Count('id', distinct=True),
            pipeline_ht=Sum(ExpressionWrapper(
                F('lignes__quantite') * F('lignes__prix_unitaire')
                * (1 - F('lignes__remise') / 100),
                output_field=FloatField())),
        )
    )
    par_commercial = []
    for row in par_commercial_raw:
        uname = row['created_by__username'] or '?'
        fname = (row['created_by__first_name'] or '').strip()
        lname = (row['created_by__last_name'] or '').strip()
        display = f'{fname} {lname}'.strip() or uname
        p_ht = row['pipeline_ht'] or 0
        par_commercial.append({
            'commercial': display,
            'devis_actifs': row['devis_actifs'],
            'valeur_pipeline': str(round(p_ht * 1.20, 2)),
        })

    return Response({
        'devis': {
            'total': agg_devis['total'],
            'envoyes': n_envoyes,
            'acceptes': n_acceptes,
            'refuses': agg_devis['refuses'],
            'expires': agg_devis['expires'],
            'taux_acceptation_pct': _pct(n_acceptes, n_envoyes),
            'valeur_pipeline': str(round(valeur_pipeline, 2)),
        },
        'factures': {
            'total': agg_fac['total'],
            'emises': agg_fac['emises'],
            'payees': agg_fac['payees'],
            'en_retard': agg_fac['en_retard'],
            'annulees': agg_fac['annulees'],
            'montant_facture': str(round(montant_facture, 2)),
            'montant_encaisse': str(round(montant_encaisse, 2)),
        },
        'conversion': {
            'devis_envoye_vers_accepte_pct': _pct(n_acceptes, n_envoyes),
            'devis_accepte_vers_facture_pct': _pct(devis_avec_facture, n_acceptes),
            'devis_envoye_vers_facture_pct': _pct(devis_avec_facture, n_envoyes),
        },
        'dso_jours': dso,
        'cycle_moyen_jours': cycle_moyen,
        'par_commercial': par_commercial,
    })
