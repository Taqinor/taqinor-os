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


# VX211 — [BACKEND léger] table STATIQUE (jamais du ML) de l'effort estimé
# par `kind` de « Ma file » — alimente le départage optionnel « Victoires
# rapides d'abord » côté frontend. Fermé, aligné sur les 6 `kind` actuels
# (`activite`, `approbation`, `mention`, `relance`, `lead_chaud`,
# `devis_expire`) ; un `kind` non listé retombe sur `'moyen'`.
_EFFORT_ESTIME_PAR_KIND = {
    'mention': 'faible',     # marquer lu / ouvrir — 1 clic
    'approbation': 'faible',  # décider — déjà 1 clic via /approbations
    'activite': 'moyen',
    'relance': 'moyen',
    'lead_chaud': 'eleve',    # premier contact à froid — plus long
    'devis_expire': 'eleve',  # relance devis + suivi
    # VX214 — kinds d'EXÉCUTION.
    'chantier_assigne': 'eleve',          # prise en main d'un chantier entier
    'intervention_du_jour': 'moyen',
    'da_approuvee_a_commander': 'faible',  # passer la commande — rapide
    'ticket_transfere': 'moyen',
}


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
        # VX214 — `ma_file` est la file de travail PER-USER (scopée
        # `request.user` côté serveur, comme `mine`) : tout rôle authentifié
        # voit la SIENNE, y compris un technicien `normal` (chantiers/
        # interventions affectés). Sans ça la file d'exécution VX214 est 403.
        if self.action in ('list', 'retrieve', 'mine', 'ma_file'):
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
        # VX85(a) — un item snoozé (`snoozed_until` dans le futur) est exclu
        # tant que non échu ; il revient de lui-même à l'heure dite, avec sa
        # `due_date` d'origine intacte (le snooze n'y touche jamais).
        qs = qs.filter(
            models.Q(snoozed_until__isnull=True)
            | models.Q(snoozed_until__lte=timezone.now().date()))
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

    @action(detail=False, methods=['get'], url_path='ma-file')
    def ma_file(self, request):
        """VX83 — « Ma file » : LA file de travail unique, cross-module.

        Une seule liste unifiée de tout ce qui attend l'utilisateur, agrégée à
        partir des sources DÉJÀ existantes (jamais un nouvel agrégateur, jamais
        une nouvelle app inbox — décision d'architecture VX83) :

          * les 3 buckets d'activités (``mine`` — en retard / aujourd'hui /
            à venir), y compris les à-faire personnels (XKB4) ;
          * les approbations décidables par l'utilisateur — via l'agrégateur
            existant ``reporting.approbations`` (jamais forké) ;
          * les mentions non lues (notifications ``chat_mention``) avec leur
            ``link`` — via ``notifications.selectors`` (jamais un import de ses
            models) ;
          * pour le rôle commercial : relances dues / leads chauds jamais
            contactés / devis proches d'expiration — via ``crm.selectors``.

        Chaque item porte ``{kind, title, due, link, urgency, montant?}`` ; la
        liste est renvoyée classée plus-urgent-d'abord, avec un total unique et
        un en-tête compté. Tout est scopé société + visibilité côté serveur.
        """
        from .serializers import activity_state
        company = _company(request)

        items = []

        # ── 1) Activités de l'utilisateur (les 3 buckets) ──────────────────
        acts = _scoped(Activity.objects.select_related(
            'activity_type', 'content_type'), request.user).filter(
            assigned_to=request.user, done=False)
        # VX85(a) — même exclusion snooze que `mine` : une file cohérente.
        acts = acts.filter(
            models.Q(snoozed_until__isnull=True)
            | models.Q(snoozed_until__lte=timezone.now().date()))
        nb_retard = nb_aujourdhui = 0
        for act in acts:
            data = ActivitySerializer(act, context={'request': request}).data
            st = activity_state(act.due_date, act.done)
            if st == 'overdue':
                urgency = 'overdue'
                nb_retard += 1
            elif st == 'today':
                urgency = 'today'
                nb_aujourdhui += 1
            else:
                urgency = 'upcoming'
            items.append({
                'kind': 'activite',
                'title': data.get('summary') or data.get('activity_type_nom')
                or 'Activité',
                'due': act.due_date,
                'link': _ma_file_activity_link(data),
                'urgency': urgency,
                'activity_id': act.id,
            })

        # ── 2) Approbations décidables par l'utilisateur ───────────────────
        nb_approbations = 0
        if company is not None:
            try:
                from apps.reporting import approbations as appro
                appro_items = []
                for source in appro._SOURCE_LOADERS:
                    appro_items.extend(appro._SOURCE_LOADERS[source](company))
                appro._enrichir_urgence(appro_items, company)
                # VX210(b) — masque les items SNOOZÉS depuis « Ma file »
                # (`SnoozedItem`, jamais retiré de l'inbox dédiée
                # `/approbations` elle-même — seule la FILE respecte le
                # snooze). Best-effort : une erreur ne masque rien.
                try:
                    from apps.notifications import selectors as notif_selectors
                    snoozed = notif_selectors.approbations_snoozees_actives(
                        request.user, company)
                except Exception:  # pragma: no cover - défensif
                    snoozed = set()
                for it in appro_items:
                    key = (it.get('source'), str(it.get('id')))
                    if key in snoozed:
                        continue
                    nb_approbations += 1
                    items.append({
                        'kind': 'approbation',
                        'title': it.get('libelle') or 'Approbation',
                        'due': it.get('cree_le'),
                        'link': '/approbations',
                        'urgency': 'overdue' if it.get('en_retard') else 'today',
                        'source': it.get('source'),
                        'source_id': it.get('id'),
                    })
            except Exception:  # pragma: no cover - défensif, jamais de 500
                pass

        # ── 3) Mentions non lues (notifications chat_mention) ──────────────
        for it in _ma_file_mentions(request.user, company):
            items.append(it)

        # ── 4) File commerciale (relances / leads chauds / devis) ──────────
        if company is not None:
            try:
                from apps.crm.selectors import ma_file_commercial_items
                items.extend(ma_file_commercial_items(company, request.user))
            except Exception:  # pragma: no cover - défensif
                pass

        # ── 5) VX214 — kinds d'EXÉCUTION (jamais une 2ᵉ boîte) ──────────────
        # Un chantier assigné, une intervention du jour, une DA approuvée à
        # commander, un ticket transféré n'apparaissaient dans AUCUNE boîte.
        # Reshape imposé (grand-verdict) : PAS de nouvel endpoint/écran — ces
        # kinds rejoignent le MÊME `ma-file/`, via une fonction lecture-seule
        # `selectors.affectations_pour(user)` par app cible (MÊME contrat
        # `{kind, title, due, link, urgency}` que le bloc 4 ci-dessus).
        if company is not None:
            try:
                from apps.installations.selectors import (
                    affectations_pour as installations_affectations_pour,
                )
                items.extend(installations_affectations_pour(request.user))
            except Exception:  # pragma: no cover - défensif
                pass
            try:
                from apps.sav.selectors import (
                    affectations_pour as sav_affectations_pour,
                )
                items.extend(sav_affectations_pour(request.user))
            except Exception:  # pragma: no cover - défensif
                pass

        # VX211 — [BACKEND léger] `effort_estime` DÉTERMINISTE par `kind`
        # (table statique, jamais du ML) : alimente un tri secondaire
        # OPTIONNEL côté frontend (« Victoires rapides d'abord »,
        # `frontend/src/features/queue/queueViews.js`) — un simple
        # DÉPARTAGE entre items d'urgence égale, jamais un remplacement du
        # tri d'urgence lui-même.
        for it in items:
            it['effort_estime'] = _EFFORT_ESTIME_PAR_KIND.get(
                it.get('kind'), 'moyen')

        # Classement plus-urgent-d'abord : en retard, puis aujourd'hui, puis
        # à venir ; à urgence égale, échéance la plus proche d'abord (les items
        # sans échéance en dernier de leur groupe). Tri stable.
        rang = {'overdue': 0, 'today': 1, 'upcoming': 2}

        def _due_key(due):
            if due is None:
                return (1, '')
            return (0, str(due))

        items.sort(key=lambda it: (
            rang.get(it.get('urgency'), 3), _due_key(it.get('due'))))

        return Response({
            'items': items,
            'total': len(items),
            'resume': {
                'en_retard': nb_retard,
                'aujourdhui': nb_aujourdhui,
                'approbations': nb_approbations,
            },
        })

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

    @action(detail=True, methods=['post'], url_path='snooze',
            permission_classes=[IsResponsableOrAdmin])
    def snooze(self, request, pk=None):
        """VX85(a) — « ⏰ Plus tard » : reporte NON DESTRUCTIVEMENT.

        Pose `snoozed_until` (l'activité disparaît de `mine`/`ma-file` jusqu'à
        cette date) sans jamais toucher `due_date` — le vrai changement
        d'échéance reste la mise à jour normale de `due_date` (bouton
        « Reporter »). Corps : `{"snoozed_until": "YYYY-MM-DD",
        "snooze_trigger_event": "client_reply:42"}` ; `snoozed_until`
        `null`/absent annule le snooze (l'item redevient visible
        immédiatement, y compris le déclencheur).

        VX210(c) — `snooze_trigger_event` optionnel (choix fermé, voir
        `services.valid_snooze_trigger_event`) : réveille l'item dès que cet
        événement métier survient, MÊME avant `snoozed_until` (le premier des
        deux gagne — cf. `services.reveiller_snoozes`)."""
        from .services import snooze_activity, valid_snooze_trigger_event
        act = self.get_object()
        raw = request.data.get('snoozed_until')
        trigger = (request.data.get('snooze_trigger_event') or '').strip()
        if not valid_snooze_trigger_event(trigger):
            return Response({'snooze_trigger_event': 'Déclencheur invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        d = None
        if raw:
            from django.utils.dateparse import parse_date
            d = parse_date(str(raw))
            if d is None:
                return Response({'snoozed_until': 'Date invalide.'},
                                status=status.HTTP_400_BAD_REQUEST)
        snooze_activity(act, d, trigger)
        return Response(ActivitySerializer(act).data)

    @action(detail=False, methods=['post'], url_path='snooze-approbation',
            permission_classes=[IsResponsableOrAdmin])
    def snooze_approbation(self, request):
        """VX210(b) — snooze/réaffiche un item HÉTÉROGÈNE d'approbation
        (5 sources de `reporting.approbations`) depuis « Ma file », via la
        table générique `SnoozedItem` (patron `ApprovalReminderState` — jamais
        un import direct des modèles des 5 sources).

        Corps : `{"source": "installations", "id": 5,
        "snoozed_until": "YYYY-MM-DD"}` ; `snoozed_until` `null`/absent annule
        le snooze. Vérifie que l'item existe RÉELLEMENT parmi les items en
        attente de la société (jamais un `source`/`id` arbitraire)."""
        company = _company(request)
        if company is None:
            return Response({'detail': 'Accès refusé.'},
                            status=status.HTTP_403_FORBIDDEN)
        from apps.reporting import approbations as appro
        source = request.data.get('source')
        obj_id = request.data.get('id')
        if source not in appro._SOURCE_LOADERS or not obj_id:
            return Response({'detail': 'Source ou id invalide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        matches = [
            it for it in appro._SOURCE_LOADERS[source](company)
            if str(it.get('id')) == str(obj_id)]
        if not matches:
            return Response({'detail': 'Introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)

        # VX210(b) — écriture EXCLUSIVEMENT via `notifications.services`
        # (jamais un import direct de `SnoozedItem` ici, même convention que
        # `notify()` déjà utilisé ailleurs dans ce fichier).
        from apps.notifications.services import (
            snooze_approbation_item, unsnooze_approbation_item,
        )
        raw = request.data.get('snoozed_until')
        if raw:
            from django.utils.dateparse import parse_date
            d = parse_date(str(raw))
            if d is None:
                return Response({'snoozed_until': 'Date invalide.'},
                                status=status.HTTP_400_BAD_REQUEST)
            snooze_approbation_item(company, request.user, source, obj_id, d)
        else:
            unsnooze_approbation_item(request.user, source, obj_id)
        return Response({'ok': True})

    def perform_update(self, serializer):
        # VX85(c) — détecte un changement d'`assigned_to` AVANT de sauver (le
        # travail ne doit jamais tomber entre deux personnes en silence) :
        # notifie le NOUVEAU propriétaire avec un `link` profond, une fois la
        # sauvegarde confirmée. Best-effort — n'échoue jamais la requête.
        instance = serializer.instance
        old_assigned_id = instance.assigned_to_id if instance else None
        act = serializer.save()
        new_assigned_id = act.assigned_to_id
        if new_assigned_id and new_assigned_id != old_assigned_id:
            _notify_reassignment(act, self.request.user)


def _notify_reassignment(act, actor):
    """VX85(c) — notifie le nouveau `assigned_to` d'une activité réaffectée.

    Best-effort (jamais d'exception remontée) : company/link/notify passent
    tous par leurs conventions habituelles (jamais un import de modèle
    étranger, `link` dérivé de la MÊME table que `_ma_file_activity_link`)."""
    try:
        user = act.assigned_to
        if user is None or (actor is not None and user.id == actor.id):
            return
        from apps.notifications.models import EventType as ET
        from apps.notifications.services import notify
        link = _deep_link(act.content_type, act.object_id)
        actor_label = getattr(actor, 'username', '') or 'Quelqu\'un'
        notify(
            user, ET.LEAD_ASSIGNED,
            f'{actor_label} vous a assigné une activité',
            body=act.summary or '', link=link, company=act.company)
    except Exception:  # pragma: no cover - défensif, jamais de 500
        pass


def _deep_link(content_type, object_id):
    """Lien profond vers l'enregistrement parent, à partir de son
    ``ContentType``/``object_id`` bruts — MÊME mapping que
    ``_ma_file_activity_link``/``targetLink`` (MesActivitesPage.jsx), pour que
    mentions/followers/réaffectation naviguent exactement comme « Ma file »."""
    if content_type is None or object_id is None:
        return None
    label = f'{content_type.app_label}.{content_type.model}'
    if label == 'crm.lead':
        return f'/crm/leads?lead={object_id}'
    if label == 'crm.client':
        return '/crm'
    if label == 'installations.installation':
        return '/chantiers'
    if label == 'sav.ticket':
        return '/sav'
    return None


def _ma_file_activity_link(data):
    """VX83 — lien profond vers l'enregistrement parent d'une activité, dérivé
    du ``target_model``/``object_id`` du serializer (miroir serveur du
    ``targetLink`` frontend). None pour un à-faire personnel (sans cible)."""
    model = data.get('target_model')
    oid = data.get('object_id')
    if model == 'crm.lead' and oid:
        return f'/crm/leads?lead={oid}'
    if model == 'crm.client':
        return '/crm'
    if model == 'installations.installation':
        return '/chantiers'
    if model == 'sav.ticket':
        return '/sav'
    return None


def _ma_file_mentions(user, company):
    """VX83 — mentions non lues de l'utilisateur (notifications
    ``chat_mention``), au format d'item de « Ma file » avec leur ``link``.

    Lecture cross-app EXCLUSIVEMENT via ``notifications.selectors`` (jamais un
    import de ``apps.notifications.models`` — convention selectors). Best-effort :
    aucune mention / app absente ⇒ liste vide, jamais une erreur qui casse la
    file."""
    if company is None:
        return []
    try:
        from apps.notifications import selectors as notif_selectors
        rows = notif_selectors.mentions_non_lues(user, company)
    except Exception:  # pragma: no cover - défensif
        return []
    out = []
    for n in rows:
        out.append({
            'kind': 'mention',
            'title': getattr(n, 'title', None) or 'Vous avez été mentionné',
            'due': getattr(n, 'created_at', None),
            'link': getattr(n, 'link', '') or None,
            'urgency': 'today',
            'notification_id': getattr(n, 'id', None),
        })
    return out


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


def _notify_mentions(body, author, company, content_type=None, object_id=None):
    """Notifie les utilisateurs mentionnés via @username (best-effort).

    VX85(b) — passe désormais `link` (même mapping que
    `_ma_file_activity_link`/`targetLink`) : avant ce fix la mention n'était
    cliquable nulle part (absente de toute file), `content_type`/`object_id`
    sont optionnels pour ne rien casser des appelants sans cible connue."""
    mentions = _parse_mentions(body)
    if not mentions:
        return
    try:
        from django.contrib.auth import get_user_model
        from apps.notifications.models import EventType as ET
        from apps.notifications.services import notify
        User = get_user_model()
        link = _deep_link(content_type, object_id)
        for username in mentions:
            try:
                user = User.objects.get(username=username, company=company)
                if user == author:
                    continue  # pas d'auto-notification
                notify(
                    user, ET.LEAD_ASSIGNED,  # réutilise l'event le plus proche
                    f'{author.username} vous a mentionné',
                    body=body[:200],
                    link=link,
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
        # VX85(b) — content_type/object_id passés pour un lien cliquable.
        _notify_mentions(
            comment.body, request.user, company,
            content_type=ct, object_id=comment.object_id)
        # XKB34 — notifie les followers de la cible sur une nouvelle note de
        # chatter (best-effort, jamais l'auteur lui-même). VX85(b) — `link`
        # même mapping, la notification followers devient cliquable aussi.
        from .services import notify_followers
        notify_followers(
            content_type=ct, object_id=comment.object_id,
            title=f'{request.user.username} a ajouté une note',
            body=comment.body[:200], exclude_user=request.user,
            link=_deep_link(ct, comment.object_id))
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
        # SCA42 — clé préfixée par société pour les NOUVEAUX uploads
        # (attachments/{company_id}/…). Les anciens objets gardent leur clé.
        meta, err = store_attachment(file, company=company)
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
