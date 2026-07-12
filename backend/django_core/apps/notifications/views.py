"""N75 — API des notifications, strictement par utilisateur.

TenantMixin scope déjà par société ; on RESTREINT en plus au destinataire
courant pour que personne ne voie les notifications d'autrui. La société ET le
destinataire/utilisateur sont posés côté serveur, jamais lus du corps.
"""
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import (
    action, api_view, permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAdminRole, IsAnyRole

from .models import (
    Annonce, EventType, Holiday, Notification, NotificationPreference,
    NotificationRoutingRule, PushSubscription, WhatsAppTemplate,
    WorkingHoursConfig,
)
from .serializers import (
    AnnonceSerializer, HolidaySerializer, NotificationPreferenceSerializer,
    NotificationRoutingRuleSerializer, NotificationSerializer,
    WhatsAppTemplateSerializer, WorkingHoursConfigSerializer,
)
from .services import (
    acknowledge_annonce, annonce_compliance_report, merged_preferences,
    publish_annonce, resolve_vapid_keys, set_template_approval_status,
    submit_template_for_approval,
)


class NotificationViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Mes notifications in-app : liste (filtre `unread`), détail, comptage,
    marquage lu / tout lu. Aucune création via l'API (les notifications naissent
    du moteur côté serveur). Lecture/gestion : tout rôle, ses notifications."""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        # Scope société (TenantMixin) PUIS destinataire courant : un utilisateur
        # ne voit jamais que ses propres notifications.
        qs = super().get_queryset().filter(recipient=self.request.user)
        params = self.request.query_params
        unread = params.get('unread')
        if unread in ('1', 'true', 'True'):
            qs = qs.filter(read=False)
        return qs

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        from . import severity as severity_module
        qs = self.get_queryset().filter(read=False)
        count = qs.count()
        # VX208(b) — deux compteurs distincts : ACTIONS (rouge, badge cloche)
        # vs INFOS (point gris) — un `DIGEST` (ou tout event non-action) ne
        # doit JAMAIS gonfler le badge d'actions. Additif : `unread` reste le
        # total inchangé pour les consommateurs existants.
        actions = sum(
            1 for et in qs.values_list('event_type', flat=True)
            if severity_module.is_action(et))
        return Response({
            'unread': count, 'actions': actions, 'infos': count - actions,
        })

    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        if not notif.read:
            notif.read = True
            notif.read_at = timezone.now()
            notif.save(update_fields=['read', 'read_at'])
        return Response(self.get_serializer(notif).data)

    @action(detail=True, methods=['post'], url_path='unread')
    def mark_unread(self, request, pk=None):
        notif = self.get_object()
        if notif.read:
            notif.read = False
            notif.read_at = None
            notif.save(update_fields=['read', 'read_at'])
        return Response(self.get_serializer(notif).data)

    @action(detail=False, methods=['post'], url_path='read-all')
    def mark_all_read(self, request):
        # VX208(c) — capture les ids AVANT la mise à jour : un « Annuler »
        # exact restaure PRÉCISÉMENT ces notifications (pas « toutes les non
        # lues au moment du clic », qui pourrait en inclure de nouvelles
        # arrivées entre-temps). `read-all` cesse d'être irréversible.
        ids = list(
            self.get_queryset().filter(read=False).values_list('id', flat=True))
        now = timezone.now()
        updated = self.get_queryset().filter(id__in=ids).update(
            read=True, read_at=now)
        return Response({'updated': updated, 'ids': ids})


class NotificationPreferenceViewSet(TenantMixin, viewsets.ViewSet):
    """Préférences de canaux par événement, propres à l'utilisateur courant.

    GET liste les préférences EFFECTIVES de tous les événements (défauts +
    lignes stockées). PUT/PATCH met à jour celle d'un événement (upsert). On ne
    fabrique pas de viewset CRUD complet : l'UI manipule une grille événement ×
    canaux."""
    permission_classes = [IsAnyRole]

    def list(self, request):
        return Response(merged_preferences(request.user))

    def update(self, request, pk=None):
        """Upsert d'une préférence pour `pk` = clé d'événement."""
        return self._upsert(request, pk)

    def partial_update(self, request, pk=None):
        return self._upsert(request, pk)

    def _upsert(self, request, event_type):
        if event_type not in EventType.values:
            return Response(
                {'detail': "Type d'événement inconnu."},
                status=status.HTTP_400_BAD_REQUEST)
        pref, _ = NotificationPreference.objects.get_or_create(
            user=request.user, event_type=event_type,
            defaults={'company': request.user.company})
        # Société toujours alignée côté serveur sur celle de l'utilisateur.
        if pref.company_id != request.user.company_id:
            pref.company = request.user.company
        data = request.data
        for field in ('in_app', 'whatsapp', 'email'):
            if field in data:
                pref.__dict__[field] = bool(data[field])
        pref.save()
        return Response(NotificationPreferenceSerializer(pref).data)


class NotificationRoutingRuleViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG4 — CRUD des règles de routage de notifications (admin uniquement).

    Lecture : tout rôle (l'UI des paramètres de notification est accessible
    à tous). Écriture : admin seulement (créer/modifier/supprimer les règles).
    Tout est scopé à la société (TenantMixin). company est posée côté serveur."""
    queryset = NotificationRoutingRule.objects.all()
    serializer_class = NotificationRoutingRuleSerializer
    READ_ACTIONS = ['list', 'retrieve']

    def get_permissions(self):
        if self.action in self.READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        event_type = self.request.query_params.get('event_type')
        if event_type:
            qs = qs.filter(event_type=event_type)
        enabled = self.request.query_params.get('enabled')
        if enabled in ('0', '1', 'true', 'false'):
            qs = qs.filter(enabled=enabled in ('1', 'true'))
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


# ─────────────────────────────────────────────────────────────────────────────
# N92 — Web push (PWA). Endpoints d'opt-in par appareil. company + user sont
# TOUJOURS posés côté serveur (jamais lus du corps). La clé publique VAPID est
# publique par nature (exposée au navigateur) ; les autres routes exigent un
# utilisateur authentifié.

class WorkingHoursConfigViewSet(viewsets.ViewSet):
    """FG5 — Config des jours ouvrés : GET (lecture) + PUT/PATCH (upsert).

    Singleton par société : GET renvoie la config effective (défauts si absente).
    PUT/PATCH crée ou met à jour la ligne de la société courante.
    Lecture : tout rôle. Écriture : admin seulement. company posée côté serveur.
    Pas de TenantMixin (ViewSet sans queryset) : scoping manuel via request.user.company."""
    permission_classes = [IsAnyRole]

    def _get_or_default_data(self, company):
        cfg = WorkingHoursConfig.objects.filter(company=company).first()
        if cfg is not None:
            return WorkingHoursConfigSerializer(cfg).data
        return {
            'id': None,
            'working_days': WorkingHoursConfig.DEFAULT_WORKING_DAYS,
            'hours_per_day': '8.00',
            'updated_at': None,
        }

    def list(self, request):
        return Response(self._get_or_default_data(request.user.company))

    def update(self, request, pk=None):
        return self._upsert(request)

    def partial_update(self, request, pk=None):
        return self._upsert(request)

    def _upsert(self, request):
        if not IsAdminRole().has_permission(request, self):
            return Response(
                {'detail': 'Réservé aux administrateurs.'},
                status=status.HTTP_403_FORBIDDEN)
        company = request.user.company
        cfg, _ = WorkingHoursConfig.objects.get_or_create(
            company=company,
            defaults={'working_days': WorkingHoursConfig.DEFAULT_WORKING_DAYS})
        serializer = WorkingHoursConfigSerializer(
            cfg, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class HolidayViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG5 — CRUD des jours fériés, scopé à la société courante.

    Lecture : tout rôle. Écriture/Suppression : admin seulement.
    company posée côté serveur dans perform_create.
    Filtre optionnel : ?year=2025 pour n'obtenir que les fériés actifs en 2025
    (date.year == 2025 OU recurrent_annuel)."""
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    READ_ACTIONS = ['list', 'retrieve']

    def get_permissions(self):
        if self.action in self.READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        year = self.request.query_params.get('year')
        if year:
            try:
                yr = int(year)
                from django.db.models import Q
                qs = qs.filter(Q(date__year=yr) | Q(recurrent_annuel=True))
            except (ValueError, TypeError):
                pass
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class WhatsAppTemplateViewSet(TenantMixin, viewsets.ModelViewSet):
    """XMKT25 — Registre des gabarits BSP + cycle d'approbation Meta.

    Lecture : tout rôle (pour la sélection dans une campagne). Écriture
    (créer/soumettre/décider) : admin seulement. company posée côté serveur.
    Une campagne ne peut choisir qu'un gabarit `statut_approbation=approuve`
    (appliqué côté service `approved_templates_for`, pas ici — ce viewset gère
    le registre lui-même)."""
    queryset = WhatsAppTemplate.objects.all()
    serializer_class = WhatsAppTemplateSerializer
    READ_ACTIONS = ['list', 'retrieve']

    def get_permissions(self):
        if self.action in self.READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut_approbation')
        if statut:
            qs = qs.filter(statut_approbation=statut)
        groupe = self.request.query_params.get('groupe')
        if groupe:
            qs = qs.filter(groupe=groupe)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        """Soumet le gabarit à l'approbation Meta (gated, no-op sans jeton)."""
        tpl = self.get_object()
        submit_template_for_approval(tpl, user=request.user)
        tpl.refresh_from_db()
        return Response(self.get_serializer(tpl).data)

    @action(detail=True, methods=['post'], url_path='decision')
    def decision(self, request, pk=None):
        """Saisie manuelle du statut d'approbation (retour Meta Business Manager).

        Corps : { statut_approbation: 'approuve'|'rejete', motif_rejet? }."""
        tpl = self.get_object()
        statut = request.data.get('statut_approbation')
        if statut not in WhatsAppTemplate.StatutApprobation.values:
            return Response(
                {'detail': "Statut d'approbation invalide."},
                status=status.HTTP_400_BAD_REQUEST)
        set_template_approval_status(
            tpl, statut, motif_rejet=request.data.get('motif_rejet', ''))
        tpl.refresh_from_db()
        return Response(self.get_serializer(tpl).data)


class AnnonceViewSet(TenantMixin, viewsets.ModelViewSet):
    """XKB5 — Annonces internes ciblées et programmées.

    Lecture : tout rôle (dashboard + écran annonces). Écriture (créer/publier/
    modifier/supprimer) : admin seulement. company + auteur posés côté serveur.
    `?active=1` restreint aux annonces publiées et non expirées (pour le
    bandeau/carte du dashboard)."""
    queryset = Annonce.objects.all()
    serializer_class = AnnonceSerializer
    READ_ACTIONS = ['list', 'retrieve']
    # accuser_lecture : « J'ai lu et compris » est ouvert à tout rôle
    # destinataire — seules création/édition/publication/conformité restent
    # réservées à l'admin (voir docstrings des actions ci-dessous).
    ANY_ROLE_ACTIONS = READ_ACTIONS + ['accuser_lecture']

    def get_permissions(self):
        if self.action in self.ANY_ROLE_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('active') in ('1', 'true', 'True'):
            now = timezone.now()
            from django.db.models import Q
            qs = qs.filter(publiee=True).filter(
                Q(date_expiration__isnull=True) | Q(date_expiration__gt=now))
        epinglee = self.request.query_params.get('epinglee')
        if epinglee in ('0', '1', 'true', 'false'):
            qs = qs.filter(epinglee=epinglee in ('1', 'true'))
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company, auteur=self.request.user)

    @action(detail=True, methods=['post'], url_path='publier')
    def publier(self, request, pk=None):
        """Publie immédiatement l'annonce (idempotent si déjà publiée)."""
        annonce = self.get_object()
        publish_annonce(annonce)
        annonce.refresh_from_db()
        return Response(self.get_serializer(annonce).data)

    # ── XKB6 — Accusé de lecture obligatoire + rapport de conformité ────────

    @action(detail=True, methods=['post'], url_path='accuser-lecture',
            permission_classes=[IsAnyRole])
    def accuser_lecture(self, request, pk=None):
        """« J'ai lu et compris » — tout rôle destinataire peut confirmer."""
        annonce = self.get_object()
        acknowledge_annonce(annonce, request.user)
        return Response({'lu': True})

    @action(detail=True, methods=['get'], url_path='conformite')
    def conformite(self, request, pk=None):
        """Rapport de conformité : qui a confirmé, quand, qui manque (admin)."""
        annonce = self.get_object()
        return Response(annonce_compliance_report(annonce))


# ─────────────────────────────────────────────────────────────────────────────
# FG5 — Endpoint de vérification des helpers de calendrier.

@api_view(['GET'])
@permission_classes([IsAnyRole])
def calendar_check(request):
    """FG5 — Diagnostic rapide : renvoie is_jour_ouvre pour la date demandée.

    Query param : ?date=2025-01-01 (défaut : aujourd'hui).
    Utile pour les tests d'intégration et le débogage de la config."""
    from datetime import date as _date
    from .calendar_utils import is_jour_ouvre, prochain_jour_ouvre
    date_str = request.query_params.get('date', '')
    try:
        d = _date.fromisoformat(date_str) if date_str else _date.today()
    except ValueError:
        return Response({'detail': 'Format de date invalide. Utilisez YYYY-MM-DD.'},
                        status=status.HTTP_400_BAD_REQUEST)
    company = request.user.company
    ouvre = is_jour_ouvre(d, company)
    next_ouvre = prochain_jour_ouvre(d, company)
    return Response({
        'date': d.isoformat(),
        'is_jour_ouvre': ouvre,
        'prochain_jour_ouvre': next_ouvre.isoformat(),
    })


# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def vapid_public_key(request):
    """Clé publique VAPID pour l'abonnement côté navigateur.

    Publique par nature. Chaîne vide tant que rien n'est configuré → le front
    sait alors que le push n'est pas disponible (NO-OP). Avec l'auto-génération
    (N109), renvoie la clé publique du singleton VAPID si aucune clé d'env."""
    return Response({'public_key': resolve_vapid_keys()[0]})


@api_view(['POST'])
@permission_classes([IsAnyRole])
def push_subscribe(request):
    """Enregistre (upsert) l'abonnement push de l'appareil courant.

    Corps attendu : { endpoint, keys: { p256dh, auth } } (format PushManager).
    company + user sont FORCÉS sur l'utilisateur courant. Idempotent par
    endpoint : un ré-abonnement met simplement à jour les clés."""
    data = request.data or {}
    endpoint = (data.get('endpoint') or '').strip()
    keys = data.get('keys') or {}
    p256dh = (keys.get('p256dh') or data.get('p256dh') or '').strip()
    auth = (keys.get('auth') or data.get('auth') or '').strip()
    if not endpoint or not p256dh or not auth:
        return Response(
            {'detail': 'Abonnement push incomplet.'},
            status=status.HTTP_400_BAD_REQUEST)
    sub, _created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'company': request.user.company,
            'user': request.user,
            'p256dh': p256dh,
            'auth': auth,
        })
    return Response({'id': sub.id}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def attention_summary(request):
    """VX207 — décompte canonique UNIQUE d'attention pour l'utilisateur courant.

    Après VX83/84/86 il existait ≥4 dérivations de compteur calculées par des
    chemins différents (badge cloche = ``derivedTotal + feedUnread``, en-tête
    Ma file, ``useApprobationsCount`` VX86, badge sidebar) sans garantie de
    convergence. Cet endpoint renvoie le décompte canonique en réutilisant
    EXACTEMENT les mêmes fonctions que « Ma file »
    (``apps.records.views.ActivityViewSet.ma_file``) — jamais une 2ᵉ
    dérivation : les 3 buckets d'activités assignées via ``records.models.
    Activity`` + ``records.serializers.activity_state`` (même filtre snooze),
    les approbations décidables via l'agrégateur ``reporting.approbations``
    (mêmes ``_SOURCE_LOADERS``, jamais forké), les mentions non lues via
    ``notifications.selectors.mentions_non_lues`` (même sélecteur cross-app).

    Scopé recipient/assigned_to = ``request.user`` (jamais un autre
    utilisateur, jamais une autre société)."""
    from django.db.models import Q

    from . import selectors as notif_selectors

    company = request.user.company if request.user.company_id else None

    en_retard = aujourdhui = 0
    if company is not None:
        from apps.records.models import Activity
        from apps.records.serializers import activity_state

        qs = Activity.objects.filter(
            company=company, assigned_to=request.user, done=False,
        ).filter(
            Q(snoozed_until__isnull=True)
            | Q(snoozed_until__lte=timezone.now().date()))
        for act in qs.only('due_date', 'done'):
            st = activity_state(act.due_date, act.done)
            if st == 'overdue':
                en_retard += 1
            elif st == 'today':
                aujourdhui += 1

    nb_approbations = 0
    if company is not None:
        try:
            from apps.reporting import approbations as appro
            for source in appro._SOURCE_LOADERS:
                nb_approbations += len(appro._SOURCE_LOADERS[source](company))
        except Exception:  # pragma: no cover - défensif, jamais de 500
            pass

    nb_mentions = 0
    try:
        nb_mentions = notif_selectors.mentions_non_lues(
            request.user, company).count()
    except Exception:  # pragma: no cover - défensif
        pass

    return Response({
        'actions_dues': en_retard + aujourdhui + nb_approbations,
        'en_retard': en_retard,
        'aujourdhui': aujourdhui,
        'approbations': nb_approbations,
        'mentions_non_lues': nb_mentions,
    })


@api_view(['POST'])
@permission_classes([IsAnyRole])
def push_unsubscribe(request):
    """Supprime l'abonnement push de l'appareil courant (par endpoint).

    Borné à l'utilisateur courant : on ne supprime jamais l'abonnement d'autrui."""
    endpoint = (request.data or {}).get('endpoint', '').strip()
    if not endpoint:
        return Response(
            {'detail': 'Endpoint manquant.'},
            status=status.HTTP_400_BAD_REQUEST)
    deleted, _ = PushSubscription.objects.filter(
        user=request.user, endpoint=endpoint).delete()
    return Response({'deleted': deleted})
