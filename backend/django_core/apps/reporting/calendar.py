"""N84 — Calendrier / agenda (lecture seule + replanification ciblée).

Agrège sur une fenêtre de dates les évènements planifiés de l'app : poses
prévues et mises en service (chantiers), interventions terrain, visites de
maintenance préventive (calculées à la volée, cohérent T7) et activités de
suivi. Tout est borné à la société de l'utilisateur. La replanification
(« glisser pour reprogrammer ») n'agit que sur les dates réellement éditables
— jamais sur une visite de maintenance, qui est calculée.
"""
from datetime import date, datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.core import signing
from django.http import HttpResponse
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

# Types éditables (une date stockée) → replanifiables par glisser-déposer.
EDITABLE_TYPES = {'pose', 'mise_en_service', 'intervention', 'activite'}

# FG6 — jeton ICS stable par utilisateur. On signe l'id utilisateur avec la
# SECRET_KEY (django.core.signing) sous un sel dédié : pas d'expiration (l'URL
# d'abonnement reste valable pour Google/Outlook), non devinable, et révocable
# globalement par rotation de la SECRET_KEY. Aucun nouveau modèle, aucune
# migration, aucune dépendance.
_ICS_SALT = 'reporting.calendar.ics.v1'


def _co_filter(user):
    """kwargs de filtrage société, ou None si accès interdit."""
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


def _parse_date(value, fallback):
    try:
        return date.fromisoformat((value or '').strip())
    except (ValueError, TypeError):
        return fallback


def _user_label(u):
    if u is None:
        return ''
    full = (getattr(u, 'get_full_name', lambda: '')() or '').strip()
    return full or getattr(u, 'username', '') or ''


@api_view(['GET'])
@permission_classes([IsAnyRole])
def calendar_events(request):
    """Évènements du calendrier sur ``?from=&to=`` (défaut : mois courant ±).

    Filtres optionnels : ``?assignee=<user_id>`` et ``?types=pose,activite``.
    Réponse : ``{from, to, events:[{id,type,type_label,title,date,assignee_id,
    assignee_nom,editable,link_type,link_id}]}``.
    """
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    today = date.today()
    start = _parse_date(request.query_params.get('from'),
                        today - timedelta(days=31))
    end = _parse_date(request.query_params.get('to'),
                      today + timedelta(days=92))
    if end < start:
        start, end = end, start

    assignee = request.query_params.get('assignee')
    try:
        assignee_id = int(assignee) if assignee not in (None, '') else None
    except (TypeError, ValueError):
        assignee_id = None

    raw_types = (request.query_params.get('types') or '').split(',')
    wanted = {t.strip() for t in raw_types if t.strip()}

    def want(type_key):
        return not wanted or type_key in wanted

    events = []

    from apps.installations.models import Installation, Intervention

    # ── Poses prévues + mises en service (chantiers) ──────────────────────
    inst_qs = Installation.objects.filter(**co).select_related(
        'technicien_responsable', 'client')
    if want('pose'):
        qs = inst_qs.filter(date_pose_prevue__gte=start,
                            date_pose_prevue__lte=end)
        if assignee_id:
            qs = qs.filter(technicien_responsable_id=assignee_id)
        for i in qs:
            events.append({
                'id': f'pose-{i.id}', 'type': 'pose',
                'type_label': 'Pose prévue',
                'title': f"Pose — {i.reference}",
                'date': i.date_pose_prevue.isoformat(),
                'assignee_id': i.technicien_responsable_id,
                'assignee_nom': _user_label(i.technicien_responsable),
                'editable': True, 'obj_id': i.id,
                'link_type': 'chantier', 'link_id': i.id,
            })
    if want('mise_en_service'):
        qs = inst_qs.filter(date_mise_en_service__gte=start,
                            date_mise_en_service__lte=end)
        if assignee_id:
            qs = qs.filter(technicien_responsable_id=assignee_id)
        for i in qs:
            events.append({
                'id': f'mes-{i.id}', 'type': 'mise_en_service',
                'type_label': 'Mise en service',
                'title': f"Mise en service — {i.reference}",
                'date': i.date_mise_en_service.isoformat(),
                'assignee_id': i.technicien_responsable_id,
                'assignee_nom': _user_label(i.technicien_responsable),
                'editable': True, 'obj_id': i.id,
                'link_type': 'chantier', 'link_id': i.id,
            })

    # ── Interventions terrain ─────────────────────────────────────────────
    if want('intervention'):
        qs = (Intervention.objects.filter(**co)
              .select_related('technicien')
              .filter(date_prevue__gte=start, date_prevue__lte=end))
        if assignee_id:
            qs = qs.filter(technicien_id=assignee_id)
        for iv in qs:
            events.append({
                'id': f'intervention-{iv.id}', 'type': 'intervention',
                'type_label': 'Intervention',
                'title': iv.get_type_intervention_display(),
                'date': iv.date_prevue.isoformat(),
                'assignee_id': iv.technicien_id,
                'assignee_nom': _user_label(iv.technicien),
                'editable': True, 'obj_id': iv.id,
                'link_type': 'chantier', 'link_id': iv.installation_id,
            })

    # ── Visites de maintenance préventive (calculées) ─────────────────────
    # Les visites de maintenance n'ont pas de responsable assigné : un filtre
    # par responsable ne doit donc PAS les masquer en silence — on les garde
    # visibles (sans assignee) même quand ?assignee= est posé.
    if want('visite_maintenance'):
        from apps.sav.models import ContratMaintenance
        contrats = (ContratMaintenance.objects.filter(**co, actif=True)
                    .select_related('client'))
        for ct in contrats:
            d = ct.prochaine_visite()
            if d and start <= d <= end:
                nom = getattr(ct.client, 'nom', '') or ''
                events.append({
                    'id': f'visite-{ct.id}', 'type': 'visite_maintenance',
                    'type_label': 'Visite de maintenance',
                    'title': f"Maintenance — {nom}".strip(' —'),
                    'date': d.isoformat(),
                    'assignee_id': None, 'assignee_nom': '',
                    'editable': False, 'obj_id': ct.id,
                    'link_type': 'contrat', 'link_id': ct.id,
                })

    # ── Activités de suivi (records.Activity ouvertes) ────────────────────
    if want('activite'):
        from apps.records.models import Activity
        qs = (Activity.objects.filter(**co, done=False,
                                      due_date__gte=start, due_date__lte=end)
              .select_related('assigned_to'))
        if assignee_id:
            qs = qs.filter(assigned_to_id=assignee_id)
        for a in qs:
            events.append({
                'id': f'activite-{a.id}', 'type': 'activite',
                'type_label': 'Activité',
                'title': a.summary or 'Activité',
                'date': a.due_date.isoformat(),
                'assignee_id': a.assigned_to_id,
                'assignee_nom': _user_label(a.assigned_to),
                'editable': True, 'obj_id': a.id,
                'link_type': 'activite', 'link_id': a.id,
            })

    events.sort(key=lambda e: e['date'])
    return Response({
        'from': start.isoformat(), 'to': end.isoformat(),
        'events': events,
    })


@api_view(['POST'])
@permission_classes([IsResponsableOrAdmin])
def calendar_reschedule(request):
    """Replanifie un évènement à date éditable (glisser-déposer).

    Corps : ``{type, id, date}`` où ``id`` est l'identifiant de l'objet sous-
    jacent (pas l'id composite de l'évènement). Refuse les types calculés
    (visite de maintenance). Borné société, écriture journalisée par les
    modèles concernés via leurs patrons existants.
    """
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    type_key = (request.data.get('type') or '').strip()
    obj_id = request.data.get('id')
    new_date = _parse_date(request.data.get('date'), None)
    if type_key not in EDITABLE_TYPES:
        return Response({'detail': 'Type non replanifiable.'}, status=400)
    if new_date is None:
        return Response({'detail': 'Date invalide (AAAA-MM-JJ).'}, status=400)

    from apps.installations.models import Installation, Intervention
    from apps.records.models import Activity

    try:
        if type_key in ('pose', 'mise_en_service'):
            inst = Installation.objects.filter(**co).get(pk=obj_id)
            field = ('date_pose_prevue' if type_key == 'pose'
                     else 'date_mise_en_service')
            setattr(inst, field, new_date)
            inst.save(update_fields=[field])
        elif type_key == 'intervention':
            iv = Intervention.objects.filter(**co).get(pk=obj_id)
            iv.date_prevue = new_date
            iv.save(update_fields=['date_prevue'])
        else:  # activite
            act = Activity.objects.filter(**co).get(pk=obj_id)
            act.due_date = new_date
            act.save(update_fields=['due_date'])
    except (Installation.DoesNotExist, Intervention.DoesNotExist,
            Activity.DoesNotExist):
        return Response({'detail': 'Introuvable.'}, status=404)

    return Response({'ok': True, 'date': new_date.isoformat()})


# ── FG6 — flux ICS / iCal par utilisateur ────────────────────────────────────

def make_ics_token(user):
    """Jeton signé stable pour l'utilisateur (sans expiration)."""
    return signing.dumps(user.pk, salt=_ICS_SALT)


def resolve_ics_token(token):
    """Retourne l'utilisateur du jeton signé, ou None si invalide."""
    if not token:
        return None
    try:
        user_id = signing.loads(token, salt=_ICS_SALT)
    except signing.BadSignature:
        return None
    User = get_user_model()
    try:
        user = User.objects.select_related('company').get(pk=user_id)
    except User.DoesNotExist:
        return None
    if not user.is_active:
        return None
    return user


def _user_calendar_events(user):
    """Évènements planifiés de l'utilisateur, bornés à sa société.

    Poses / mises en service / interventions qui lui sont assignées, ses
    activités de suivi ouvertes, et les visites de maintenance préventive de la
    société (calculées, sans responsable — visibles pour tous les techniciens,
    cohérent avec la vue JSON). Fenêtre large : passé proche → un an.
    """
    co = _co_filter(user)
    if co is None:
        return []

    today = date.today()
    start = today - timedelta(days=31)
    end = today + timedelta(days=366)
    events = []

    from apps.installations.models import Installation, Intervention

    inst_qs = Installation.objects.filter(
        **co, technicien_responsable_id=user.pk).select_related('client')
    for i in inst_qs.filter(date_pose_prevue__gte=start,
                            date_pose_prevue__lte=end):
        events.append({
            'uid': f'pose-{i.id}', 'date': i.date_pose_prevue,
            'summary': f"Pose — {i.reference}",
            'description': f"Pose prévue — {getattr(i.client, 'nom', '') or ''}".strip(' —'),
        })
    for i in inst_qs.filter(date_mise_en_service__gte=start,
                            date_mise_en_service__lte=end):
        events.append({
            'uid': f'mes-{i.id}', 'date': i.date_mise_en_service,
            'summary': f"Mise en service — {i.reference}",
            'description': f"Mise en service — {getattr(i.client, 'nom', '') or ''}".strip(' —'),
        })

    iv_qs = (Intervention.objects.filter(**co, technicien_id=user.pk)
             .filter(date_prevue__gte=start, date_prevue__lte=end))
    for iv in iv_qs:
        events.append({
            'uid': f'intervention-{iv.id}', 'date': iv.date_prevue,
            'summary': iv.get_type_intervention_display(),
            'description': 'Intervention terrain',
        })

    from apps.sav.models import ContratMaintenance
    contrats = (ContratMaintenance.objects.filter(**co, actif=True)
                .select_related('client'))
    for ct in contrats:
        d = ct.prochaine_visite()
        if d and start <= d <= end:
            nom = getattr(ct.client, 'nom', '') or ''
            events.append({
                'uid': f'visite-{ct.id}', 'date': d,
                'summary': f"Maintenance — {nom}".strip(' —'),
                'description': 'Visite de maintenance préventive',
            })

    from apps.records.models import Activity
    acts = (Activity.objects.filter(**co, done=False,
                                    assigned_to_id=user.pk,
                                    due_date__gte=start, due_date__lte=end))
    for a in acts:
        events.append({
            'uid': f'activite-{a.id}', 'date': a.due_date,
            'summary': a.summary or 'Activité',
            'description': 'Activité de suivi',
        })

    return events


def _ics_escape(text):
    """Échappe une valeur de texte iCal (RFC 5545 §3.3.11)."""
    return (str(text or '')
            .replace('\\', '\\\\').replace(';', '\\;')
            .replace(',', '\\,').replace('\n', '\\n').replace('\r', ''))


def _fold(line):
    """Plie une ligne ICS à 75 octets (RFC 5545 §3.1)."""
    raw = line.encode('utf-8')
    if len(raw) <= 75:
        return line
    out, chunk = [], b''
    for ch in line:
        enc = ch.encode('utf-8')
        if len(chunk) + len(enc) > 75:
            out.append(chunk.decode('utf-8'))
            chunk = b' ' + enc
        else:
            chunk += enc
    out.append(chunk.decode('utf-8'))
    return '\r\n'.join(out)


def build_ics(user, events, *, calname=None):
    """Construit un VCALENDAR valide.

    VX245 — chaque `ev` supporte DEUX formes (jamais mélangées dans le
    même dict) :
      * journée entière (comportement HISTORIQUE, flux d'abonnement N84) —
        `ev['date']` (objet `date`) ;
      * évènement PONCTUEL horodaté (VX245, ex. un rendez-vous) —
        `ev['start_dt']`/`ev['end_dt']` (objets `datetime` AWARE, UTC ou
        convertis) : émet `DTSTART`/`DTEND` en heure précise au lieu de
        `VALUE=DATE`.
    `calname` : remplace le `X-WR-CALNAME` par défaut (utile pour un .ics
    à évènement unique — « Rendez-vous Taqinor » plutôt que le nom d'agenda
    complet de l'abonnement)."""
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Taqinor OS//Agenda//FR',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        f'X-WR-CALNAME:{_ics_escape(calname or f"Agenda Taqinor — {_user_label(user)}")}',
    ]
    for ev in events:
        lines.append('BEGIN:VEVENT')
        lines.append(f"UID:{ev['uid']}@taqinor")
        lines.append(f'DTSTAMP:{stamp}')
        if 'start_dt' in ev:
            start = ev['start_dt'].astimezone(timezone.utc)
            end = ev['end_dt'].astimezone(timezone.utc)
            lines.append(f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}")
            lines.append(f"DTEND:{end.strftime('%Y%m%dT%H%M%SZ')}")
        else:
            d = ev['date']
            dnext = d + timedelta(days=1)
            lines.append(f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{dnext.strftime('%Y%m%d')}")
        lines.append(f"SUMMARY:{_ics_escape(ev['summary'])}")
        lines.append(f"DESCRIPTION:{_ics_escape(ev.get('description', ''))}")
        if ev.get('location'):
            lines.append(f"LOCATION:{_ics_escape(ev['location'])}")
        lines.append('END:VEVENT')
    lines.append('END:VCALENDAR')
    body = '\r\n'.join(_fold(ln) for ln in lines) + '\r\n'
    return body


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def calendar_ics(request):
    """Flux iCal du calendrier de l'utilisateur — ``?token=<jeton signé>``.

    Authentifié par le jeton signé (pas de session) pour que Google/Outlook
    puissent s'abonner. Borné à la société de l'utilisateur résolu du jeton ;
    jamais d'évènements d'une autre société/d'un autre utilisateur.
    """
    user = resolve_ics_token(request.query_params.get('token'))
    if user is None:
        return HttpResponse('Jeton invalide.', status=401,
                            content_type='text/plain; charset=utf-8')
    events = _user_calendar_events(user)
    body = build_ics(user, events)
    resp = HttpResponse(body, content_type='text/calendar; charset=utf-8')
    resp['Content-Disposition'] = 'inline; filename="taqinor-agenda.ics"'
    return resp


@api_view(['GET'])
@permission_classes([IsAnyRole])
def calendar_ics_subscription(request):
    """URL d'abonnement ICS de l'utilisateur courant (authentifié par session).

    Réponse : ``{token, url}`` — l'URL absolue ``…/calendar.ics?token=…`` à
    coller dans Google Agenda / Outlook (« S'abonner au calendrier »).
    """
    token = make_ics_token(request.user)
    path = '/api/django/reporting/calendar.ics?token=' + token
    return Response({'token': token, 'url': request.build_absolute_uri(path)})
