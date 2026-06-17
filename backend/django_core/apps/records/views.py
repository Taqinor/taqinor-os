"""API des activités planifiées et pièces jointes (génériques).

Tout est scopé société côté serveur. Lecture : tout rôle. Écriture d'activités
et ajout de pièces jointes : Responsable (Commerciale) ou Admin. Suppression de
pièce jointe et gestion des types d'activité : Admin.
"""
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import (
    action, api_view, permission_classes,
)
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)

from .models import Activity, ActivityType, Attachment
from .serializers import (
    ActivitySerializer, ActivityTypeSerializer, AttachmentSerializer,
    resolve_target,
)
from .storage import delete_attachment, fetch_attachment, store_attachment


def _company(request):
    return request.user.company if request.user.company_id else None


def _scoped(qs, user):
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()


# ── Types d'activité ────────────────────────────────────────────────
class ActivityTypeViewSet(viewsets.ModelViewSet):
    serializer_class = ActivityTypeSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        return _scoped(ActivityType.objects.all(), self.request.user)

    def perform_create(self, serializer):
        serializer.save(company=_company(self.request))


# ── Activités ───────────────────────────────────────────────────────
class ActivityViewSet(viewsets.ModelViewSet):
    serializer_class = ActivitySerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'mine'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = _scoped(
            Activity.objects.select_related(
                'activity_type', 'assigned_to', 'content_type'),
            self.request.user)
        model = self.request.query_params.get('model')
        oid = self.request.query_params.get('id')
        if model and oid:
            try:
                ct, _ = resolve_target(model, oid, _company(self.request))
            except ValueError:
                return qs.none()
            qs = qs.filter(content_type=ct, object_id=oid)
        if self.request.query_params.get('open') == '1':
            qs = qs.filter(done=False)
        return qs

    def create(self, request, *args, **kwargs):
        company = _company(request)
        try:
            ct, _obj = resolve_target(
                request.data.get('model'), request.data.get('id'), company)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(
            company=company, content_type=ct,
            object_id=request.data.get('id'),
            created_by=request.user,
            assigned_to=ser.validated_data.get('assigned_to') or request.user,
        )
        return Response(ser.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def mine(self, request):
        """Cockpit « Mes activités » : ouvertes de l'utilisateur, bucketées."""
        from .serializers import activity_state
        qs = _scoped(Activity.objects.select_related(
            'activity_type', 'content_type'), request.user).filter(
            assigned_to=request.user, done=False)
        buckets = {'en_retard': [], 'aujourdhui': [], 'a_venir': []}
        for act in qs:
            data = ActivitySerializer(act).data
            st = activity_state(act.due_date, act.done)
            if st == 'overdue':
                buckets['en_retard'].append(data)
            elif st == 'today':
                buckets['aujourdhui'].append(data)
            else:
                buckets['a_venir'].append(data)
        return Response(buckets)

    @action(detail=True, methods=['post'], url_path='done',
            permission_classes=[IsResponsableOrAdmin])
    def marquer_fait(self, request, pk=None):
        act = self.get_object()
        if not act.done:
            act.done = True
            act.done_at = timezone.now()
            act.done_by = request.user
            act.save(update_fields=['done', 'done_at', 'done_by'])
            _log_done_to_chatter(act, request.user)
        # Planifier la suite si demandé.
        nxt = request.data.get('next')
        created = None
        if isinstance(nxt, dict) and nxt.get('activity_type'):
            try:
                created = Activity.objects.create(
                    company=act.company,
                    content_type=act.content_type, object_id=act.object_id,
                    activity_type_id=nxt['activity_type'],
                    summary=nxt.get('summary', ''),
                    note=nxt.get('note', ''),
                    due_date=nxt.get('due_date') or None,
                    assigned_to=act.assigned_to or request.user,
                    created_by=request.user)
            except Exception:
                created = None
        return Response({
            'activity': ActivitySerializer(act).data,
            'next': ActivitySerializer(created).data if created else None,
        })

    def perform_update(self, serializer):
        serializer.save()


def _log_done_to_chatter(activity, user):
    """Écrit « Activité 'X' faite par … » dans l'Historique du parent.

    Best-effort par type de cible ; n'échoue jamais la requête.
    """
    ct = activity.content_type
    label = activity.activity_type.nom
    actor = getattr(user, 'username', '?')
    body = f"Activité « {label} » faite par {actor}"
    try:
        target = activity.content_object
        if target is None:
            return
        if (ct.app_label, ct.model) == ('crm', 'lead'):
            from apps.crm import activity as crm_activity
            crm_activity.log_note(target, user, body)
        elif (ct.app_label, ct.model) == ('installations', 'installation'):
            from apps.installations import activity as inst_activity
            if hasattr(inst_activity, 'log_note'):
                inst_activity.log_note(target, user, body)
        elif (ct.app_label, ct.model) == ('sav', 'ticket'):
            from apps.sav import activity as sav_activity
            if hasattr(sav_activity, 'log_note'):
                sav_activity.log_note(target, user, body)
    except Exception:
        pass


# ── Pièces jointes ──────────────────────────────────────────────────
class AttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = AttachmentSerializer
    parser_classes = [MultiPartParser]

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'download'):
            return [IsAnyRole()]
        if self.action == 'destroy':
            return [IsAdminRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = _scoped(
            Attachment.objects.select_related('uploaded_by', 'content_type'),
            self.request.user)
        model = self.request.query_params.get('model')
        oid = self.request.query_params.get('id')
        if model and oid:
            try:
                ct, _ = resolve_target(model, oid, _company(self.request))
            except ValueError:
                return qs.none()
            qs = qs.filter(content_type=ct, object_id=oid)
        return qs

    def create(self, request, *args, **kwargs):
        company = _company(request)
        try:
            ct, _obj = resolve_target(
                request.data.get('model'), request.data.get('id'), company)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        meta, err = store_attachment(file)
        if err:
            return Response({'detail': err},
                            status=status.HTTP_400_BAD_REQUEST)
        phase = (request.data.get('phase') or '').strip().lower()
        if phase not in ('', 'avant', 'pendant', 'apres'):
            phase = ''
        att = Attachment.objects.create(
            company=company, content_type=ct, object_id=request.data.get('id'),
            uploaded_by=request.user, phase=phase, **meta)
        return Response(AttachmentSerializer(att).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """B1 — relaie le fichier via Django (MÊME ORIGINE), authentifié par le
        cookie, au lieu d'une URL présignée pointant vers l'hôte interne MinIO
        (injoignable depuis le navigateur → icône fichier cassé). Sert en
        ligne (inline) pour que PDF et images s'ouvrent dans le navigateur."""
        att = self.get_object()  # déjà borné à la société par get_queryset
        data, err = fetch_attachment(att.file_key)
        if err:
            return Response({'detail': err}, status=status.HTTP_404_NOT_FOUND)
        resp = HttpResponse(
            data, content_type=att.mime or 'application/octet-stream')
        safe_name = (att.filename or 'fichier').replace('"', '')
        resp['Content-Disposition'] = f'inline; filename="{safe_name}"'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp

    def perform_destroy(self, instance):
        delete_attachment(instance.file_key)
        instance.delete()


@api_view(['GET'])
@permission_classes([IsAnyRole])
def attachments_count(request):
    """Compteur de pièces jointes pour un enregistrement (badge trombone)."""
    model = request.query_params.get('model')
    oid = request.query_params.get('id')
    if not (model and oid):
        return Response({'count': 0})
    try:
        ct, _ = resolve_target(model, oid, _company(request))
    except ValueError:
        return Response({'count': 0})
    n = _scoped(Attachment.objects.all(), request.user).filter(
        content_type=ct, object_id=oid).count()
    return Response({'count': n})
