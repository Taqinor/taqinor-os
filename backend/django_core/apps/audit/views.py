"""API de lecture du Journal d'activité (Feature G).

Deux endpoints, tous deux réservés à la permission « Voir le Journal
d'activité » (Directeur par défaut) :

* ``stats`` — comptes d'actions bucketés à l'heure (Jour), au jour (Semaine /
  Mois), en Africa/Casablanca, avec filtres (utilisateurs, type d'action,
  module/modèle, plage de dates) ;
* la liste paginée filtrable (plus récent d'abord, mêmes filtres + recherche),
  reliant chaque ligne à l'objet sous-jacent quand il existe.

Tout est company-scopé côté serveur. Les horodatages sont stockés en UTC ; le
bucketing et l'affichage se font en Africa/Casablanca.
"""
from datetime import datetime, timedelta, date as date_cls
from zoneinfo import ZoneInfo

from django.contrib.contenttypes.models import ContentType
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from authentication.permissions import IsAdminRole

from .models import AuditLog
from .selectors import reconstruct_as_of
from .serializers import AuditLogSerializer

CASABLANCA = ZoneInfo('Africa/Casablanca')


class CanViewActivityLog(BasePermission):
    """Permission « journal_activite_voir » (Directeur par défaut)."""
    message = "Accès au Journal d'activité non autorisé."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated
            and getattr(user, 'can_view_activity_log', False)
        )


def _company_qs(request):
    qs = AuditLog.objects.select_related('user', 'content_type')
    user = request.user
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


def _apply_filters(qs, params):
    """Filtres communs au graphe et à la liste."""
    users = params.getlist('user') or params.getlist('user[]')
    if users:
        qs = qs.filter(user_id__in=[u for u in users if str(u).isdigit()])
    actions = params.getlist('action') or params.getlist('action[]')
    if actions:
        qs = qs.filter(action__in=actions)
    module = params.get('module')
    if module:
        qs = qs.filter(content_type__app_label=module)
    model = params.get('model')
    if model:
        qs = qs.filter(content_type__model=model)
    # VX98 — deep-link « Historique » depuis une fiche : pré-filtre sur CET
    # objet (index (content_type, object_id)). object_id est un CharField.
    object_id = params.get('object_id')
    if object_id:
        qs = qs.filter(object_id=str(object_id))
    date_from = _parse_date(params.get('from'))
    date_to = _parse_date(params.get('to'))
    if date_from:
        start = datetime.combine(date_from, datetime.min.time(), CASABLANCA)
        qs = qs.filter(timestamp__gte=start)
    if date_to:
        end = datetime.combine(
            date_to, datetime.min.time(), CASABLANCA) + timedelta(days=1)
        qs = qs.filter(timestamp__lt=end)
    search = (params.get('search') or '').strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(object_repr__icontains=search)
            | Q(detail__icontains=search)
            | Q(actor_username__icontains=search)
        )
    return qs


def _parse_date(value):
    if not value:
        return None
    try:
        return date_cls.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _period_bounds(period, anchor):
    """(start_local, end_local, granularity, bucket_keys) pour Jour/Semaine/Mois."""
    if period == 'semaine':
        monday = anchor - timedelta(days=anchor.weekday())
        start = datetime.combine(monday, datetime.min.time(), CASABLANCA)
        end = start + timedelta(days=7)
        keys = [(monday + timedelta(days=i)) for i in range(7)]
        return start, end, 'day', [d.isoformat() for d in keys]
    if period == 'mois':
        first = anchor.replace(day=1)
        if first.month == 12:
            nxt = first.replace(year=first.year + 1, month=1)
        else:
            nxt = first.replace(month=first.month + 1)
        start = datetime.combine(first, datetime.min.time(), CASABLANCA)
        end = datetime.combine(nxt, datetime.min.time(), CASABLANCA)
        ndays = (nxt - first).days
        keys = [(first + timedelta(days=i)).isoformat() for i in range(ndays)]
        return start, end, 'day', keys
    # Jour (défaut) : 24 buckets horaires.
    start = datetime.combine(anchor, datetime.min.time(), CASABLANCA)
    end = start + timedelta(days=1)
    keys = [f'{h:02d}' for h in range(24)]
    return start, end, 'hour', keys


@api_view(['GET'])
@permission_classes([CanViewActivityLog])
def stats(request):
    params = request.query_params
    period = (params.get('period') or 'jour').lower()
    anchor = _parse_date(params.get('date')) or datetime.now(CASABLANCA).date()
    start, end, granularity, keys = _period_bounds(period, anchor)

    qs = _company_qs(request).filter(timestamp__gte=start, timestamp__lt=end)
    # Filtres optionnels (user/action/module/model/search) — pas la plage 'from/to'
    # qui est gérée par la période ici.
    qs = _apply_filters_no_range(qs, params)

    counts = {k: 0 for k in keys}
    by_action = {k: {} for k in keys}
    total = 0
    for ts, action in qs.values_list('timestamp', 'action'):
        local = ts.astimezone(CASABLANCA)
        key = f'{local.hour:02d}' if granularity == 'hour' \
            else local.date().isoformat()
        if key not in counts:
            continue
        counts[key] += 1
        by_action[key][action] = by_action[key].get(action, 0) + 1
        total += 1

    buckets = [
        {'key': k, 'count': counts[k], 'by_action': by_action[k]}
        for k in keys
    ]
    return Response({
        'period': period,
        'date': anchor.isoformat(),
        'granularity': granularity,
        'total': total,
        'buckets': buckets,
    })


def _apply_filters_no_range(qs, params):
    """Comme _apply_filters mais sans la plage from/to (déjà bornée par la
    période du graphe)."""
    users = params.getlist('user') or params.getlist('user[]')
    if users:
        qs = qs.filter(user_id__in=[u for u in users if str(u).isdigit()])
    actions = params.getlist('action') or params.getlist('action[]')
    if actions:
        qs = qs.filter(action__in=actions)
    module = params.get('module')
    if module:
        qs = qs.filter(content_type__app_label=module)
    model = params.get('model')
    if model:
        qs = qs.filter(content_type__model=model)
    # VX98 — deep-link « Historique » depuis une fiche : pré-filtre sur CET objet.
    object_id = params.get('object_id')
    if object_id:
        qs = qs.filter(object_id=str(object_id))
    search = (params.get('search') or '').strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(object_repr__icontains=search)
            | Q(detail__icontains=search)
            | Q(actor_username__icontains=search)
        )
    return qs


@api_view(['GET'])
@permission_classes([CanViewActivityLog])
def meta(request):
    """Données pour peindre la barre de filtres : utilisateurs de la société +
    types d'action + modules/objets disponibles."""
    from authentication.models import CustomUser
    user = request.user
    users_qs = CustomUser.objects.all()
    if user.company_id:
        users_qs = users_qs.filter(company=user.company)
    elif not user.is_superuser:
        users_qs = users_qs.none()
    return Response({
        'users': [
            {'id': u.id, 'username': u.username}
            for u in users_qs.order_by('username')
        ],
        'actions': [
            {'value': v, 'label': lbl}
            for v, lbl in AuditLog.Action.choices
        ],
        'modules': [
            {'value': 'crm', 'label': 'CRM'},
            {'value': 'ventes', 'label': 'Ventes'},
            {'value': 'installations', 'label': 'Chantiers'},
            {'value': 'sav', 'label': 'Après-vente'},
            {'value': 'stock', 'label': 'Stock'},
            {'value': 'parametres', 'label': 'Paramètres'},
            {'value': 'authentication', 'label': 'Utilisateurs'},
            {'value': 'roles', 'label': 'Rôles'},
        ],
    })


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Liste paginée filtrable du Journal d'activité (plus récent d'abord)."""
    serializer_class = AuditLogSerializer
    permission_classes = [CanViewActivityLog]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['timestamp', 'action']
    ordering = ['-timestamp']

    def get_queryset(self):
        return _apply_filters(_company_qs(self.request), self.request.query_params)


# FG23 — onglet « Sécurité » : réutilise le Journal d'activité, pré-filtré aux
# évènements de sécurité (connexion, échec de connexion, alerte). Le frontend
# peut aussi simplement passer ?action=... à AuditLogViewSet ; cet endpoint
# offre un raccourci nommé. Mêmes filtres (user/from/to/search) et même garde.
SECURITY_ACTIONS = [
    AuditLog.Action.LOGIN,
    AuditLog.Action.LOGIN_FAILED,
    AuditLog.Action.SECURITY_ALERT,
    AuditLog.Action.LOGOUT,
]


@api_view(['GET'])
@permission_classes([CanViewActivityLog])
def security_events(request):
    """Évènements de sécurité (company-scopés, plus récent d'abord).

    Filtres : ``?action=`` (restreint au sous-ensemble sécurité), ``?user=``,
    ``?from=``/``?to=``, ``?search=``, ``?limit=`` (défaut 100, max 500)."""
    qs = _apply_filters(_company_qs(request), request.query_params)
    requested = (request.query_params.getlist('action')
                 or request.query_params.getlist('action[]'))
    allowed = {a.value for a in SECURITY_ACTIONS}
    if requested:
        qs = qs.filter(action__in=[a for a in requested if a in allowed])
    else:
        qs = qs.filter(action__in=list(allowed))
    try:
        limit = min(int(request.query_params.get('limit', 100)), 500)
    except (TypeError, ValueError):
        limit = 100
    data = AuditLogSerializer(qs[:limit], many=True).data
    return Response({'count': len(data), 'results': data})


# YHARD3 — reconstruction as-of générique, lecture seule, admin/Directeur.
# ``objets/<app_label>.<model>/<id>/as-of/?date=`` (content type désigné par
# ``app_label.model`` dans l'URL, ex. ``crm.client``). Company-scopée : sans
# société sur l'utilisateur (ni superuser), renvoie 404 plutôt qu'une fuite.
@api_view(['GET'])
@permission_classes([CanViewActivityLog])
def object_as_of(request, content_type, object_id):
    try:
        app_label, model = content_type.split('.', 1)
        ct = ContentType.objects.get(app_label=app_label, model=model)
    except (ValueError, ContentType.DoesNotExist):
        return Response({'detail': 'content_type invalide'}, status=404)

    date_param = request.query_params.get('date')
    dt = parse_datetime(date_param) if date_param else None
    if date_param and dt is None:
        # Accepte aussi une simple date ISO (YYYY-MM-DD) → minuit UTC.
        parsed_date = _parse_date(date_param)
        if parsed_date is None:
            return Response({'detail': 'date invalide (ISO 8601 attendu)'}, status=400)
        dt = datetime.combine(parsed_date, datetime.min.time(), CASABLANCA)

    user = request.user
    company = user.company if user.company_id else None
    if company is None and not user.is_superuser:
        return Response({'detail': 'Non autorisé.'}, status=404)

    result = reconstruct_as_of(ct, object_id, dt=dt, company=company)
    return Response({
        'content_type': content_type,
        'object_id': str(object_id),
        'as_of': result['as_of'],
        'fields': result['fields'],
        'covered_changes': result['covered_changes'],
    })


# NTSEC15 — export CSV des évènements de sécurité (Directeur only, scopé société).
# Garde IsAdminRole (Directeur/Administrateur, y compris les comptes admin
# hérités) plutôt que CanViewActivityLog : ce dernier exige la permission fine
# ``journal_activite_voir`` et EXCLUT délibérément l'admin légacy sans rôle fin
# — or l'export est explicitement réservé au Directeur (cf. NTSEC19 accessreview,
# même palier IsAdminRole).
@api_view(['GET'])
@permission_classes([IsAdminRole])
def security_events_export(request):
    """Export CSV des évènements de sécurité de la société sur une période.

    Filtres : ``?from=``/``?to=`` (ISO). Company-scopé strict via le sélecteur
    fondation ``selectors.security_events`` ; jamais d'autre société."""
    import csv

    from django.http import HttpResponse

    from .selectors import security_events as _security_events

    user = request.user
    company = user.company if user.company_id else None
    if company is None:
        # Un superuser sans société active n'a pas de périmètre CSV défini.
        return Response({'detail': 'Aucune société active.'}, status=400)

    since = parse_datetime(request.query_params.get('from', '') or '')
    until = parse_datetime(request.query_params.get('to', '') or '')
    qs = _security_events(company, since=since, until=until)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="security_events.csv"')
    writer = csv.writer(response)
    writer.writerow(['timestamp', 'action', 'utilisateur', 'ip', 'detail'])
    for entry in qs.iterator():
        writer.writerow([
            entry.timestamp.isoformat(),
            entry.action,
            entry.actor_username or (
                entry.user.username if entry.user_id else ''),
            '',
            (entry.detail or '').replace('\n', ' '),
        ])
    return response
