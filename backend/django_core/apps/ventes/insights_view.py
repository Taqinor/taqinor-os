"""FG47 — Cash-flow / prévision des encaissements à venir.

Agrégation LECTURE SEULE, scopée société. Bucketise les montants dûs des
factures ouvertes (émises + en retard) par date d'échéance.

Buckets renvoyés :
  - en_retard  : date_echeance < aujourd'hui
  - cette_semaine : [today..today+6]
  - semaine_suivante : [today+7..today+13]
  - ce_mois : [today..fin du mois courant]
  - mois_suivant : début→fin du mois suivant
  - au_dela : tout ce qui dépasse les buckets ci-dessus
  - sans_echeance : factures actives sans date_echeance fixée
"""
from decimal import Decimal
from datetime import timedelta
import calendar

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole


def _s(d):
    return str(Decimal(d).quantize(Decimal('0.01')))


def _end_of_month(d):
    last_day = calendar.monthrange(d.year, d.month)[1]
    return d.replace(day=last_day)


def _start_of_next_month(d):
    if d.month == 12:
        return d.replace(year=d.year + 1, month=1, day=1)
    return d.replace(month=d.month + 1, day=1)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def cash_flow_forecast(request):
    """GET /ventes/insights/cash-flow/

    Prévision des encaissements scopée société. Tous montants en MAD TTC.

    Paramètres optionnels :
      - ?horizon=N  : nombre de jours à projeter (défaut 90)

    Réponse :
    {
      "buckets": {
        "en_retard":          {"montant": str, "count": int},
        "cette_semaine":       {"montant": str, "count": int},
        "semaine_suivante":    {"montant": str, "count": int},
        "ce_mois":             {"montant": str, "count": int},
        "mois_suivant":        {"montant": str, "count": int},
        "au_dela":             {"montant": str, "count": int},
        "sans_echeance":       {"montant": str, "count": int},
      },
      "total_en_cours": str,    # Somme de toutes les factures ouvertes
      "rows": [                  # Détail par facture (trié : retard d'abord, puis echéance)
        {
          "facture_reference": str,
          "client": str,
          "date_echeance": str | null,
          "montant_du": str,
          "jours_retard": int,
          "bucket": str,
        }
      ]
    }
    """
    from .models import Facture
    company = request.user.company
    today = timezone.now().date()

    # Bornes des buckets temporels.
    week_end = today + timedelta(days=6)
    next_week_start = today + timedelta(days=7)
    next_week_end = today + timedelta(days=13)
    month_end = _end_of_month(today)
    next_month_start = _start_of_next_month(today)
    next_month_end = _end_of_month(next_month_start)

    # Factures ouvertes (émises / en retard), toutes échéances.
    open_factures = (
        Facture.objects
        .filter(company=company, statut__in=('emise', 'en_retard'))
        .prefetch_related('paiements', 'avoirs', 'client')
        .order_by('date_echeance')
    )

    # Compteurs par bucket.
    buckets = {k: {'montant': Decimal('0'), 'count': 0} for k in [
        'en_retard', 'cette_semaine', 'semaine_suivante',
        'ce_mois', 'mois_suivant', 'au_dela', 'sans_echeance',
    ]}
    total = Decimal('0')
    rows = []

    for f in open_factures:
        du = f.montant_du
        if du <= 0:
            continue  # déjà soldé via paiements/avoirs

        ech = f.date_echeance
        client_name = (
            f"{f.client.nom} {f.client.prenom or ''}".strip()
            if f.client else '—'
        )

        if ech is None:
            bucket = 'sans_echeance'
        elif ech < today:
            bucket = 'en_retard'
        elif ech <= week_end:
            bucket = 'cette_semaine'
        elif ech <= next_week_end:
            bucket = 'semaine_suivante'
        elif ech <= month_end:
            bucket = 'ce_mois'
        elif next_month_start <= ech <= next_month_end:
            bucket = 'mois_suivant'
        else:
            bucket = 'au_dela'

        buckets[bucket]['montant'] += du
        buckets[bucket]['count'] += 1
        total += du

        rows.append({
            'facture_reference': f.reference,
            'client': client_name,
            'date_echeance': ech.isoformat() if ech else None,
            'montant_du': _s(du),
            'jours_retard': f.jours_retard,
            'bucket': bucket,
        })

    # Trier : retards d'abord (par date_echeance croissante), puis à venir.
    rows.sort(key=lambda r: (
        0 if r['bucket'] == 'en_retard' else 1,
        r['date_echeance'] or '9999-99-99',
    ))

    return Response({
        'buckets': {
            k: {'montant': _s(v['montant']), 'count': v['count']}
            for k, v in buckets.items()
        },
        'total_en_cours': _s(total),
        'rows': rows,
    })
