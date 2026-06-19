"""N84 — Calendrier / agenda (lecture seule + replanification ciblée).

Agrège sur une fenêtre de dates les évènements planifiés de l'app : poses
prévues et mises en service (chantiers), interventions terrain, visites de
maintenance préventive (calculées à la volée, cohérent T7) et activités de
suivi. Tout est borné à la société de l'utilisateur. La replanification
(« glisser pour reprogrammer ») n'agit que sur les dates réellement éditables
— jamais sur une visite de maintenance, qui est calculée.
"""
from datetime import date, timedelta

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

# Types éditables (une date stockée) → replanifiables par glisser-déposer.
EDITABLE_TYPES = {'pose', 'mise_en_service', 'intervention', 'activite'}


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
