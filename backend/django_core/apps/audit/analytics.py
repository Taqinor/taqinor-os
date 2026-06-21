"""FG97 — Audit-log analytics : rollups sur le journal d'activité.

Endpoint ``GET /api/django/audit/analytics/`` (gated : journal_activite_voir).

Paramètres optionnels :
  ?days=N        — fenêtre en jours (défaut 30, max 365)
  ?from=YYYY-MM-DD
  ?to=YYYY-MM-DD

Retourne :
  top_users       — Top-10 utilisateurs les plus actifs (nb actions)
  action_mix      — Répartition par type d'action (count + % du total)
  daily_counts    — Comptes par jour sur la fenêtre (pour un sparkline)
  failed_logins   — Série journalière des échecs de connexion (spike detector)
  object_churn    — Top-10 modèles par volume de modifications (create+update+delete)
"""
from datetime import date as date_cls, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import AuditLog
from .views import CanViewActivityLog

CASABLANCA = ZoneInfo('Africa/Casablanca')
MAX_DAYS = 365


def _parse_date(value):
    try:
        return date_cls.fromisoformat((value or '').strip())
    except (ValueError, TypeError):
        return None


def _window(params):
    """Retourne (start_dt, end_dt, days) en UTC."""
    d_from = _parse_date(params.get('from'))
    d_to = _parse_date(params.get('to'))
    try:
        days = min(int(params.get('days', 30)), MAX_DAYS)
        days = max(days, 1)
    except (ValueError, TypeError):
        days = 30

    today = datetime.now(CASABLANCA).date()
    if d_from:
        start = datetime.combine(d_from, datetime.min.time(), CASABLANCA)
    else:
        start = datetime.combine(today - timedelta(days=days - 1),
                                 datetime.min.time(), CASABLANCA)
    if d_to:
        end = datetime.combine(d_to + timedelta(days=1),
                               datetime.min.time(), CASABLANCA)
    else:
        end = datetime.combine(today + timedelta(days=1),
                               datetime.min.time(), CASABLANCA)
    actual_days = max((end.date() - start.date()).days, 1)
    return start, end, actual_days


@api_view(['GET'])
@permission_classes([CanViewActivityLog])
def audit_analytics(request):
    """FG97 — rollups analytiques du journal d'activité."""
    user = request.user
    qs = AuditLog.objects.all()
    if user.company_id:
        qs = qs.filter(company=user.company)
    elif not user.is_superuser:
        return Response({'detail': 'Accès refusé.'}, status=403)

    start, end, days = _window(request.query_params)
    qs = qs.filter(timestamp__gte=start, timestamp__lt=end)

    # ── Top-10 utilisateurs les plus actifs ─────────────────────────────────
    top_users = list(
        qs.exclude(actor_username='')
        .values('actor_username')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # ── Répartition par type d'action ────────────────────────────────────────
    action_counts = list(
        qs.values('action')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    total = sum(a['count'] for a in action_counts)
    action_mix = [
        {
            'action': a['action'],
            'label': dict(AuditLog.Action.choices).get(a['action'], a['action']),
            'count': a['count'],
            'pct': round(a['count'] / total * 100, 1) if total else 0,
        }
        for a in action_counts
    ]

    # ── Comptes journaliers (sparkline total) ────────────────────────────────
    all_rows = list(qs.values_list('timestamp', 'action'))
    day_counts: dict[str, int] = {}
    failed_counts: dict[str, int] = {}
    for ts, action in all_rows:
        local_date = ts.astimezone(CASABLANCA).date().isoformat()
        day_counts[local_date] = day_counts.get(local_date, 0) + 1
        if action == AuditLog.Action.LOGIN_FAILED:
            failed_counts[local_date] = failed_counts.get(local_date, 0) + 1

    # Série complète sur la fenêtre (0 si aucun log ce jour-là)
    start_date = start.date()
    daily_counts = []
    failed_logins = []
    for i in range(days):
        d = (start_date + timedelta(days=i)).isoformat()
        daily_counts.append({'date': d, 'count': day_counts.get(d, 0)})
        failed_logins.append({'date': d, 'count': failed_counts.get(d, 0)})

    # ── Top-10 modèles par churn (create + update + delete) ──────────────────
    churn_actions = {
        AuditLog.Action.CREATE,
        AuditLog.Action.UPDATE,
        AuditLog.Action.DELETE,
    }
    object_churn = list(
        qs.filter(action__in=churn_actions)
        .exclude(content_type__isnull=True)
        .values('content_type__app_label', 'content_type__model')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    return Response({
        'window_days': days,
        'from': start.date().isoformat(),
        'to': (end.date() - timedelta(days=1)).isoformat(),
        'total_entries': total,
        'top_users': top_users,
        'action_mix': action_mix,
        'daily_counts': daily_counts,
        'failed_logins': failed_logins,
        'object_churn': object_churn,
    })
