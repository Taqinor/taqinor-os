"""API des activités planifiées et pièces jointes (génériques).

Tout est scopé société côté serveur. Lecture : tout rôle. Écriture d'activités
et ajout de pièces jointes : Responsable (Commerciale) ou Admin. Suppression de
pièce jointe et gestion des types d'activité : Admin.
"""
from datetime import timedelta

from django.db import models
from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import (
    action, api_view, permission_classes,
)
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from core.selectors import get_company_object

from .models import (
    Activity, ActivityType, Attachment, Comment, Follower, Tag, TaggedItem,
)
from .serializers import (
    ActivitySerializer, ActivityTypeSerializer, AttachmentSerializer,
    ChatterActivitySerializer, CommentSerializer, FollowerSerializer,
    TaggedItemSerializer, TagSerializer, resolve_target,
)
from .storage import delete_attachment, fetch_attachment, store_attachment


# ── ARC8 — Chatter générique réutilisable (le « mail.thread » maison) ─────────
class ChatterViewSetMixin:
    """Donne à N'IMPORTE quel ``ModelViewSet`` un chatter générique adossé à
    ``records.Activity`` — deux actions ``chatter/historique`` (GET) et
    ``chatter/noter`` (POST), sur le patron de ``crm.LeadActivity``.

    - ``GET  <detail>/chatter/historique/`` : timeline (plus récent d'abord) des
      entrées de chatter générique de l'objet.
    - ``POST <detail>/chatter/noter/`` : ajoute une note manuelle (corps :
      ``body`` non vide). L'auteur ET la société sont TOUJOURS posés côté
      serveur (``request.user`` / société de l'objet) — jamais lus du corps.

    L'objet est borné à la société par le ``get_object()`` de la vue hôte (dont
    le queryset est déjà scopé société). Ces actions sont ADDITIVES : elles
    coexistent avec le journal maison éventuel de la vue (ex. l'action
    ``historique`` de ``ContratViewSet``), sur des URL distinctes."""

    @action(detail=True, methods=['get'], url_path='chatter/historique',
            permission_classes=[IsAnyRole])
    def chatter_historique(self, request, pk=None):
        from .services import chatter_qs
        target = self.get_object()
        qs = chatter_qs(target, company=_company(request))
        return Response(ChatterActivitySerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='chatter/noter',
            permission_classes=[IsResponsableOrAdmin])
    def chatter_noter(self, request, pk=None):
        from .models import Activity
        from .services import log_activity
        target = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = log_activity(
            target, Activity.Kind.NOTE, user=request.user, body=body,
            company=_company(request))
        return Response(ChatterActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)


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
        # XKB4 — un à-faire personnel n'est JAMAIS visible d'un collègue,
        # même admin/superviseur : on l'exclut sauf pour son créateur.
        qs = qs.exclude(
            models.Q(personnelle=True) & ~models.Q(created_by=self.request.user))
        model = self.request.query_params.get('model')
        oid = self.request.query_params.get('id')
        if model and oid:
            try:
                ct, _ = resolve_target(model, oid, _company(self.request))
            except ValueError:
                return qs.none()
            qs = qs.filter(content_type=ct, object_id=oid)
        elif self.request.query_params.get('personnelle') == '1':
            qs = qs.filter(personnelle=True, created_by=self.request.user)
        if self.request.query_params.get('open') == '1':
            qs = qs.filter(done=False)
        return qs

    def create(self, request, *args, **kwargs):
        company = _company(request)
        model = request.data.get('model')
        oid = request.data.get('id')
        # XKB4 — à-faire personnel : pas de cible métier (model/id absents).
        if not model and not oid:
            ser = self.get_serializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save(
                company=company, content_type=None, object_id=None,
                personnelle=True,
                created_by=request.user,
                assigned_to=ser.validated_data.get('assigned_to') or request.user,
            )
            return Response(ser.data, status=status.HTTP_201_CREATED)
        try:
            ct, _obj = resolve_target(model, oid, company)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(
            company=company, content_type=ct,
            object_id=oid,
            created_by=request.user,
            assigned_to=ser.validated_data.get('assigned_to') or request.user,
        )
        return Response(ser.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='vers-tache-projet')
    def vers_tache_projet(self, request, pk=None):
        """XKB4 — convertit un à-faire personnel en tâche projet réelle.

        Passe EXCLUSIVEMENT par ``gestion_projet.services`` (jamais un import
        de ses ``models``) : préserve la frontière cross-app (CLAUDE.md). Le
        contenu (résumé/note/échéance/assigné) est reporté sur la tâche créée.
        L'activité d'origine est marquée faite pour ne plus polluer « Mes
        activités » (mais n'est jamais supprimée)."""
        act = self.get_object()
        projet_id = request.data.get('projet_id') or request.data.get('projet')
        if not projet_id:
            return Response({'detail': 'projet_id requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        from apps.gestion_projet import services as gp_services
        try:
            tache = gp_services.creer_tache_depuis_activite(
                act, projet_id=projet_id, company=act.company or _company(request))
        except gp_services.ConversionActiviteError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        act.done = True
        act.done_at = timezone.now()
        act.done_by = request.user
        act.save(update_fields=['done', 'done_at', 'done_by'])
        return Response({
            'activity': ActivitySerializer(act).data,
            'tache_id': tache.id,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def mine(self, request):
        """Cockpit « Mes activités » : ouvertes de l'utilisateur, bucketées."""
        from .serializers import activity_state
        qs = _scoped(Activity.objects.select_related(
            'activity_type', 'content_type'), request.user).filter(
            assigned_to=request.user, done=False)
        buckets = {'en_retard': [], 'aujourdhui': [], 'a_venir': []}
        for act in qs:
            # QX25be — passe le contexte requête pour résoudre target_phone.
            data = ActivitySerializer(act, context={'request': request}).data
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
        chained = None
        suggestion = None
        first_close = not act.done
        if first_close:
            act.done = True
            act.done_at = timezone.now()
            act.done_by = request.user
            act.save(update_fields=['done', 'done_at', 'done_by'])
            _log_done_to_chatter(act, request.user)
            # ZSAL1 — enchaînement du type d'activité, UNIQUEMENT à la
            # PREMIÈRE clôture (re-clôturer une activité déjà faite ne
            # déclenche/ne suggère jamais une 2ᵉ fois — idempotence).
            chained, suggestion = _appliquer_enchainement(act, request.user)
        # Planifier la suite si demandé explicitement par le front.
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
            'chained': ActivitySerializer(chained).data if chained else None,
            'suggestion': suggestion,
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


def _appliquer_enchainement(activity, user):
    """ZSAL1 — applique le `mode_enchainement` du type d'activité clôturée.

    Renvoie ``(activite_creee_ou_None, suggestion_dict_ou_None)`` :
    - ``mode_enchainement == 'aucun'`` (défaut) : rien ne change, renvoie
      ``(None, None)`` — comportement inchangé pour tous les types existants ;
    - ``'suggerer'`` : ne crée RIEN, renvoie juste la proposition au front ;
    - ``'declencher'`` : crée EXACTEMENT une activité de suivi (même cible,
      échéance = aujourd'hui + `delai_jours`, assignée au même utilisateur).
      Appelé une seule fois par la vue (à la PREMIÈRE clôture uniquement), ce
      qui garantit l'idempotence — re-clôturer n'en crée jamais une 2ᵉ.
    """
    atype = activity.activity_type
    type_suivant = atype.type_suivant
    if not type_suivant or atype.mode_enchainement == ActivityType.ModeEnchainement.AUCUN:
        return None, None

    if atype.mode_enchainement == ActivityType.ModeEnchainement.SUGGERER:
        return None, {
            'activity_type': type_suivant.id,
            'activity_type_nom': type_suivant.nom,
            'delai_jours': atype.delai_jours,
        }

    if atype.mode_enchainement == ActivityType.ModeEnchainement.DECLENCHER:
        echeance = timezone.now().date() + timedelta(days=atype.delai_jours)
        created = Activity.objects.create(
            company=activity.company,
            content_type=activity.content_type, object_id=activity.object_id,
            activity_type=type_suivant,
            summary=type_suivant.nom,
            personnelle=activity.personnelle,
            due_date=echeance,
            assigned_to=activity.assigned_to or user,
            created_by=user)
        return created, None

    return None, None


# ── Commentaires (FG7) ──────────────────────────────────────────────
import re as _re  # noqa: E402

# Les identifiants Django autorisent `-`, `.`, `_`, `+`, `@` : le motif de
# mention doit donc couvrir un username comme « prenom-nom » (sinon `\w+`
# s'arrête au tiret et la mention n'est jamais résolue → aucune notification).
_MENTION_RE = _re.compile(r'@([\w][\w.+-]*)')


def _parse_mentions(body):
    """Retourne la liste des noms d'utilisateur mentionnés dans `body`."""
    return list(set(_MENTION_RE.findall(body or '')))


def _notify_mentions(body, author, company):
    """Notifie les utilisateurs mentionnés via @username (best-effort)."""
    mentions = _parse_mentions(body)
    if not mentions:
        return
    try:
        from django.contrib.auth import get_user_model
        from apps.notifications.models import EventType as ET
        from apps.notifications.services import notify
        User = get_user_model()
        for username in mentions:
            try:
                user = User.objects.get(username=username, company=company)
                if user == author:
                    continue  # pas d'auto-notification
                notify(
                    user, ET.LEAD_ASSIGNED,  # réutilise l'event le plus proche
                    f'{author.username} vous a mentionné',
                    body=body[:200],
                    company=company)
            except User.DoesNotExist:
                pass
    except Exception:  # pragma: no cover - défensif
        pass


class CommentViewSet(viewsets.ModelViewSet):
    """FG7 — Commentaires génériques + @mentions.

    Lecture : tout rôle. Création/modification : propriétaire ou admin.
    Suppression : admin seulement. Scopé société (company posée côté serveur)."""
    serializer_class = CommentSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        if self.action == 'destroy':
            return [IsAdminRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = _scoped(
            Comment.objects.select_related('author', 'content_type'),
            self.request.user)
        model = self.request.query_params.get('model')
        oid = self.request.query_params.get('id')
        if model and oid:
            try:
                ct, _ = resolve_target(model, oid, _company(self.request))
            except ValueError:
                return qs.none()
            qs = qs.filter(content_type=ct, object_id=oid)
        # XKB13 — ?resolved=true|false : masque/affiche les fils résolus
        # (le frontend masque les fils résolus par défaut).
        resolved = self.request.query_params.get('resolved')
        if resolved is not None:
            qs = qs.filter(resolved=resolved.lower() in ('1', 'true', 'yes'))
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
        comment = ser.save(
            company=company,
            content_type=ct,
            object_id=request.data.get('id'),
            author=request.user)
        # Notifie les @mentions (best-effort, jamais d'erreur remontée).
        _notify_mentions(comment.body, request.user, company)
        # XKB34 — notifie les followers de la cible sur une nouvelle note de
        # chatter (best-effort, jamais l'auteur lui-même).
        from .services import notify_followers
        notify_followers(
            content_type=ct, object_id=comment.object_id,
            title=f'{request.user.username} a ajouté une note',
            body=comment.body[:200], exclude_user=request.user)
        return Response(CommentSerializer(comment).data,
                        status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        serializer.save()


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

    @action(detail=True, methods=['patch'], url_path='phase',
            parser_classes=[JSONParser, MultiPartParser])
    def set_phase(self, request, pk=None):
        """N5/L5 — re-tague la phase (avant/pendant/après) d'une pièce jointe
        sans supprimer/ré-uploader le fichier. Scopé société par get_object."""
        att = self.get_object()  # déjà borné à la société par get_queryset
        phase = (request.data.get('phase') or '').strip().lower()
        if phase not in ('', 'avant', 'pendant', 'apres'):
            return Response({'phase': 'Phase invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        att.phase = phase
        att.save(update_fields=['phase'])
        return Response(AttachmentSerializer(att).data)

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


# ── Tags (FG9) ──────────────────────────────────────────────────────

class TagViewSet(viewsets.ModelViewSet):
    """FG9 — Vocabulaire de tags de la société.

    Lecture : tout rôle. Création/modification : responsable ou admin.
    Suppression : admin seulement. company posée côté serveur."""
    serializer_class = TagSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        if self.action == 'destroy':
            return [IsAdminRole()]
        return [IsResponsableOrAdmin()]

    def perform_create(self, serializer):
        serializer.save(company=_company(self.request))

    def get_queryset(self):
        qs = _scoped(Tag.objects.all(), self.request.user)
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(nom__icontains=q)
        return qs


class TaggedItemViewSet(viewsets.ModelViewSet):
    """FG9 — Associations tag ↔ enregistrement.

    Lecture : tout rôle (filtrage par model+id). Création/suppression :
    responsable ou admin. company déduite du tag (jamais du corps)."""
    serializer_class = TaggedItemSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        # TaggedItem n'a pas de company directement → filtre par tag__company.
        if user.company_id:
            qs = TaggedItem.objects.select_related(
                'tag', 'content_type').filter(tag__company=user.company)
        elif user.is_superuser:
            qs = TaggedItem.objects.select_related('tag', 'content_type').all()
        else:
            return TaggedItem.objects.none()
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
        tag_id = request.data.get('tag')
        if not tag_id:
            return Response({'detail': 'tag requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # YRBAC11 — helper canonique (company-scopé, 404 converti en 400 ici,
        # contrat de validation de ce champ inchangé).
        try:
            tag = get_company_object(Tag, tag_id, request.user)
        except Http404:
            return Response({'detail': 'Tag introuvable.'},
                            status=status.HTTP_400_BAD_REQUEST)
        item, created = TaggedItem.objects.get_or_create(
            tag=tag, content_type=ct, object_id=request.data.get('id'))
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(TaggedItemSerializer(item).data, status=code)


# ── Followers (XKB34) ────────────────────────────────────────────────
class FollowerViewSet(viewsets.ModelViewSet):
    """XKB34 — S'abonner/se désabonner d'un enregistrement.

    Lecture : tout rôle (filtrage par model+id, ou `?mine=1` pour ses propres
    abonnements). Création : tout rôle (suivre est une action personnelle,
    jamais restreinte à un rôle). Suppression : seulement son propre abonnement.
    Company posée côté serveur, jamais lue du corps de requête."""
    serializer_class = FollowerSerializer

    def get_permissions(self):
        return [IsAnyRole()]

    def get_queryset(self):
        qs = _scoped(
            Follower.objects.select_related('user', 'content_type'),
            self.request.user)
        model = self.request.query_params.get('model')
        oid = self.request.query_params.get('id')
        if model and oid:
            try:
                ct, _ = resolve_target(model, oid, _company(self.request))
            except ValueError:
                return qs.none()
            qs = qs.filter(content_type=ct, object_id=oid)
        if self.request.query_params.get('mine') == '1':
            qs = qs.filter(user=self.request.user)
        return qs

    def create(self, request, *args, **kwargs):
        company = _company(request)
        try:
            ct, _obj = resolve_target(
                request.data.get('model'), request.data.get('id'), company)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        from .services import follow
        obj = follow(
            company=company, content_type=ct,
            object_id=request.data.get('id'), user=request.user,
            sous_type=(request.data.get('sous_type') or ''))
        return Response(FollowerSerializer(obj).data,
                        status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        follower = self.get_object()
        if follower.user_id != request.user.id:
            return Response(
                {'detail': "Vous ne pouvez désabonner que vous-même."},
                status=status.HTTP_403_FORBIDDEN)
        follower.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def attachments_all(request):
    """FG10 — Centre de pièces jointes de la société.

    Retourne TOUTES les pièces jointes de la société (scopé TenantMixin),
    paginées, avec filtres optionnels :
      - mime      : filtre exact sur le type MIME (ex. 'application/pdf')
      - mime_like : filtre icontains sur le type MIME (ex. 'image' → tous les
                    types image/*)
      - phase     : 'avant' / 'pendant' / 'apres' / '' (sans phase)
      - model     : ex. 'crm.lead' (filtre sur content_type)
      - since     : date ISO 8601 (created_at >= since)

    Résultats triés du plus récent au plus ancien. Paginés à 50 par page."""
    from rest_framework.pagination import PageNumberPagination

    qs = _scoped(
        Attachment.objects.select_related('uploaded_by', 'content_type'),
        request.user
    ).order_by('-created_at', '-id')

    p = request.query_params
    mime = p.get('mime')
    if mime:
        qs = qs.filter(mime=mime)
    mime_like = p.get('mime_like')
    if mime_like:
        qs = qs.filter(mime__icontains=mime_like)
    phase = p.get('phase')
    if phase is not None:
        qs = qs.filter(phase=phase)
    model = p.get('model')
    if model:
        try:
            app_label, model_name = str(model).lower().split('.', 1)
            from django.contrib.contenttypes.models import ContentType
            ct = ContentType.objects.get(app_label=app_label, model=model_name)
            qs = qs.filter(content_type=ct)
        except (ValueError, ContentType.DoesNotExist):
            qs = qs.none()
    since = p.get('since')
    if since:
        try:
            from django.utils.dateparse import parse_datetime, parse_date
            from django.utils import timezone as tz
            dt = parse_datetime(since)
            if dt is None:
                d = parse_date(since)
                if d:
                    dt = tz.datetime(d.year, d.month, d.day, tzinfo=tz.utc)
            if dt:
                qs = qs.filter(created_at__gte=dt)
        except Exception:
            pass

    paginator = PageNumberPagination()
    paginator.page_size = 50
    page = paginator.paginate_queryset(qs, request)
    ser = AttachmentSerializer(page, many=True)
    return paginator.get_paginated_response(ser.data)


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
