"""N75 — API des notifications, strictement par utilisateur.

TenantMixin scope déjà par société ; on RESTREINT en plus au destinataire
courant pour que personne ne voie les notifications d'autrui. La société ET le
destinataire/utilisateur sont posés côté serveur, jamais lus du corps.
"""
from django.utils import timezone

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, extend_schema_view, inline_serializer,
)
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import (
    authentication_classes, action, api_view, parser_classes,
    permission_classes,
)
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from core.viewsets import CompanyScopedModelViewSet
from authentication.permissions import (
    IsAdminOrResponsableTier, IsAdminRole, IsAnyRole,
)

from .models import (
    Annonce,
    Holiday,
    MessageAccueil,
    Notification,
    NotificationPreference,
    NotificationRoutingRule,
    PushSubscription,
    WhatsAppTemplate,
    WorkingHoursConfig,
)
from .types_evenements import EventType
from .serializers import (
    AnnonceSerializer, HolidaySerializer, MessageAccueilSerializer,
    NotificationPreferenceSerializer, NotificationRoutingRuleSerializer,
    NotificationSerializer, WhatsAppTemplateSerializer,
    WorkingHoursConfigSerializer,
)
from .services import (
    acknowledge_annonce, annonce_compliance_report, merged_preferences,
    publish_annonce, resolve_vapid_keys, set_template_approval_status,
    submit_template_for_approval,
)


def _q(nom, type_, description, **kw):
    """ENF8 — paramètre de requête optionnel lu par la vue."""
    return OpenApiParameter(
        nom, type_, OpenApiParameter.QUERY, required=False,
        description=description, **kw)


_DETAIL = inline_serializer('NotificationsDetail', {
    'detail': serializers.CharField(),
})
_OK_UPDATED = inline_serializer('NotificationsToutLu', {
    'updated': serializers.IntegerField(),
    'ids': serializers.ListField(child=serializers.IntegerField()),
})
_UNREAD_COUNT = inline_serializer('NotificationsNonLues', {
    'unread': serializers.IntegerField(),
    'actions': serializers.IntegerField(),
    'infos': serializers.IntegerField(),
})
_PREFERENCE_LIGNE = inline_serializer('PreferenceEffective', many=True, fields={
    'event_type': serializers.CharField(),
    'event_label': serializers.CharField(),
    'in_app': serializers.BooleanField(),
    'whatsapp': serializers.BooleanField(),
    'email': serializers.BooleanField(),
    'push': serializers.BooleanField(),
    'routable': serializers.BooleanField(),
})
_PREFERENCE_REQUEST = inline_serializer('PreferenceEcriture', {
    'in_app': serializers.BooleanField(required=False),
    'whatsapp': serializers.BooleanField(required=False),
    'email': serializers.BooleanField(required=False),
    'push': serializers.BooleanField(required=False),
})
_PREFERENCE_ID = OpenApiParameter(
    'id', OpenApiTypes.STR, OpenApiParameter.PATH,
    enum=list(EventType.values), description="Clé du type d'événement.")
_BOOL_01 = ['0', '1', 'true', 'false']


@extend_schema_view(
    list=extend_schema(parameters=[_q(
        'unread', OpenApiTypes.STR, 'Ne garder que les non lues.',
        enum=['1', 'true', 'True'])]),
)
class NotificationViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """Mes notifications in-app : liste (filtre `unread`), détail, comptage,
    marquage lu / tout lu. Aucune création via l'API (les notifications naissent
    du moteur côté serveur). Lecture/gestion : tout rôle, ses notifications."""
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAnyRole]
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload

    def get_queryset(self):
        # Scope société (TenantMixin) PUIS destinataire courant : un utilisateur
        # ne voit jamais que ses propres notifications.
        qs = super().get_queryset().filter(recipient=self.request.user)
        # N1 — une notification DIFFÉRÉE (émise hors de la fenêtre de travail
        # de la société) n'existe pas encore pour son destinataire : ni liste,
        # ni compteur, ni « tout marquer comme lu ». Elle apparaît quand le
        # balayage `notifications.livrer_differees` remet ce champ à NULL.
        qs = qs.filter(programmee_pour__isnull=True)
        params = self.request.query_params
        unread = params.get('unread')
        if unread in ('1', 'true', 'True'):
            qs = qs.filter(read=False)
        if self.action == 'list':
            # VX209(c) — `list()` renvoyait TOUT sans borne (croissance sans
            # fin). Bornée à 90 j + non archivées (la purge quotidienne
            # supprime les lues > 60 j et archive les non-lues > 60 j — cette
            # borne est un filet de sécurité, pas le mécanisme principal).
            # Les autres actions (detail, read/unread, read-all) restent SUR
            # LA QUERYSET COMPLÈTE : un lien profond envoyé par email vers une
            # notification plus ancienne doit continuer de fonctionner.
            from datetime import timedelta as _timedelta
            horizon = timezone.now() - _timedelta(days=90)
            qs = qs.filter(archived=False, created_at__gte=horizon)
        return qs

    @extend_schema(responses=_UNREAD_COUNT)
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

    @extend_schema(request=None, responses=NotificationSerializer)
    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        if not notif.read:
            notif.read = True
            notif.read_at = timezone.now()
            notif.save(update_fields=['read', 'read_at'])
        return Response(self.get_serializer(notif).data)

    @extend_schema(request=None, responses=NotificationSerializer)
    @action(detail=True, methods=['post'], url_path='unread')
    def mark_unread(self, request, pk=None):
        notif = self.get_object()
        if notif.read:
            notif.read = False
            notif.read_at = None
            notif.save(update_fields=['read', 'read_at'])
        return Response(self.get_serializer(notif).data)

    @extend_schema(request=None, responses=_OK_UPDATED)
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


@extend_schema_view(
    list=extend_schema(responses=_PREFERENCE_LIGNE),
    update=extend_schema(
        parameters=[_PREFERENCE_ID], request=_PREFERENCE_REQUEST,
        responses=NotificationPreferenceSerializer),
    partial_update=extend_schema(
        parameters=[_PREFERENCE_ID], request=_PREFERENCE_REQUEST,
        responses=NotificationPreferenceSerializer),
)
class NotificationPreferenceViewSet(TenantMixin, viewsets.ViewSet):
    """Préférences de canaux par événement, propres à l'utilisateur courant.

    GET liste les préférences EFFECTIVES de tous les événements (défauts +
    lignes stockées). PUT/PATCH met à jour celle d'un événement (upsert). On ne
    fabrique pas de viewset CRUD complet : l'UI manipule une grille événement ×
    canaux."""
    permission_classes = [IsAnyRole]
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload
    serializer_class = NotificationPreferenceSerializer

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
        for field in ('in_app', 'whatsapp', 'email', 'push'):
            if field in data:
                pref.__dict__[field] = bool(data[field])
        pref.save()
        return Response(NotificationPreferenceSerializer(pref).data)


@extend_schema_view(list=extend_schema(parameters=[
    _q('event_type', OpenApiTypes.STR, "Type d'événement."),
    _q('enabled', OpenApiTypes.STR, 'Règles actives ou non.',
       enum=_BOOL_01)]))
class NotificationRoutingRuleViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG4 — CRUD des règles de routage de notifications (admin uniquement).

    Lecture : tout rôle (l'UI des paramètres de notification est accessible
    à tous). Écriture : admin seulement (créer/modifier/supprimer les règles).
    Tout est scopé à la société (TenantMixin). company est posée côté serveur."""
    queryset = NotificationRoutingRule.objects.all()
    serializer_class = NotificationRoutingRuleSerializer
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload
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

@extend_schema_view(
    list=extend_schema(responses=WorkingHoursConfigSerializer),
    update=extend_schema(
        parameters=[OpenApiParameter(
            'id', OpenApiTypes.STR, OpenApiParameter.PATH)],
        request=WorkingHoursConfigSerializer,
        responses=WorkingHoursConfigSerializer),
    partial_update=extend_schema(
        parameters=[OpenApiParameter(
            'id', OpenApiTypes.STR, OpenApiParameter.PATH)],
        request=WorkingHoursConfigSerializer,
        responses=WorkingHoursConfigSerializer),
)
class WorkingHoursConfigViewSet(viewsets.ViewSet):
    """FG5 — Config des jours ouvrés : GET (lecture) + PUT/PATCH (upsert).

    Singleton par société : GET renvoie la config effective (défauts si absente).
    PUT/PATCH crée ou met à jour la ligne de la société courante.
    Lecture : tout rôle. Écriture : admin seulement. company posée côté serveur.
    Pas de TenantMixin (ViewSet sans queryset) : scoping manuel via request.user.company."""
    permission_classes = [IsAnyRole]
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload
    serializer_class = WorkingHoursConfigSerializer

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


@extend_schema_view(list=extend_schema(parameters=[
    _q('year', OpenApiTypes.INT, 'Année : fériés de cette année ou récurrents.')]))
class HolidayViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG5 — CRUD des jours fériés, scopé à la société courante.

    Lecture : tout rôle. Écriture/Suppression : admin seulement.
    company posée côté serveur dans perform_create.
    Filtre optionnel : ?year=2025 pour n'obtenir que les fériés actifs en 2025
    (date.year == 2025 OU recurrent_annuel)."""
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload
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


@extend_schema_view(list=extend_schema(parameters=[
    _q('statut_approbation', OpenApiTypes.STR, "Statut d'approbation.",
       enum=list(WhatsAppTemplate.StatutApprobation.values)),
    _q('groupe', OpenApiTypes.STR, 'Groupe de gabarits.')]))
class WhatsAppTemplateViewSet(TenantMixin, viewsets.ModelViewSet):
    """XMKT25 — Registre des gabarits BSP + cycle d'approbation Meta.

    Lecture : tout rôle (pour la sélection dans une campagne). Écriture
    (créer/soumettre/décider) : admin seulement. company posée côté serveur.
    Une campagne ne peut choisir qu'un gabarit `statut_approbation=approuve`
    (appliqué côté service `approved_templates_for`, pas ici — ce viewset gère
    le registre lui-même)."""
    queryset = WhatsAppTemplate.objects.all()
    serializer_class = WhatsAppTemplateSerializer
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload
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

    @extend_schema(request=None, responses=WhatsAppTemplateSerializer)
    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        """Soumet le gabarit à l'approbation Meta (gated, no-op sans jeton)."""
        tpl = self.get_object()
        submit_template_for_approval(tpl, user=request.user)
        tpl.refresh_from_db()
        return Response(self.get_serializer(tpl).data)

    @extend_schema(
        request=inline_serializer('WhatsAppTemplateDecision', {
            'statut_approbation': serializers.ChoiceField(
                choices=list(WhatsAppTemplate.StatutApprobation.values)),
            'motif_rejet': serializers.CharField(required=False),
        }),
        responses=WhatsAppTemplateSerializer)
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


_LIGNE_LECTURE = {
    'user_id': serializers.IntegerField(),
    'username': serializers.CharField(),
}
_CONFORMITE = inline_serializer('AnnonceConformite', {
    'lus': inline_serializer('AnnonceConformiteLu', {
        **_LIGNE_LECTURE, 'date_lecture': serializers.DateTimeField(),
    }, many=True),
    'manquants': inline_serializer(
        'AnnonceConformiteManquant', _LIGNE_LECTURE, many=True),
    'total_cibles': serializers.IntegerField(),
})


@extend_schema_view(list=extend_schema(parameters=[
    _q('active', OpenApiTypes.STR, 'Publiées et non expirées seulement.',
       enum=['1', 'true', 'True']),
    _q('epinglee', OpenApiTypes.STR, 'Annonces épinglées ou non.',
       enum=_BOOL_01)]))
# Actions ouvertes à tout rôle (module-level : la garde check_action_permission_override
# lit les constantes de module pour voir que accuser_lecture n'atteint pas le repli admin).
_ANNONCE_READ_ACTIONS = ['list', 'retrieve']
_ANNONCE_ANY_ROLE_ACTIONS = _ANNONCE_READ_ACTIONS + ['accuser_lecture']


class AnnonceViewSet(TenantMixin, viewsets.ModelViewSet):
    """XKB5 — Annonces internes ciblées et programmées.

    Lecture : tout rôle (dashboard + écran annonces). Écriture (créer/publier/
    modifier/supprimer) : admin seulement. company + auteur posés côté serveur.
    `?active=1` restreint aux annonces publiées et non expirées (pour le
    bandeau/carte du dashboard)."""
    queryset = Annonce.objects.all()
    serializer_class = AnnonceSerializer
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload
    READ_ACTIONS = ['list', 'retrieve']
    # accuser_lecture : « J'ai lu et compris » est ouvert à tout rôle
    # destinataire — seules création/édition/publication/conformité restent
    # réservées à l'admin (voir docstrings des actions ci-dessous).

    def get_permissions(self):
        if self.action in _ANNONCE_ANY_ROLE_ACTIONS:
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

    @extend_schema(request=None, responses=AnnonceSerializer)
    @action(detail=True, methods=['post'], url_path='publier')
    def publier(self, request, pk=None):
        """Publie immédiatement l'annonce (idempotent si déjà publiée)."""
        annonce = self.get_object()
        publish_annonce(annonce)
        annonce.refresh_from_db()
        return Response(self.get_serializer(annonce).data)

    # ── XKB6 — Accusé de lecture obligatoire + rapport de conformité ────────

    @extend_schema(request=None, responses=inline_serializer(
        'AnnonceAccuseLecture', {'lu': serializers.BooleanField()}))
    @action(detail=True, methods=['post'], url_path='accuser-lecture',
            permission_classes=[IsAnyRole])
    def accuser_lecture(self, request, pk=None):
        """« J'ai lu et compris » — tout rôle destinataire peut confirmer."""
        annonce = self.get_object()
        acknowledge_annonce(annonce, request.user)
        return Response({'lu': True})

    @extend_schema(responses=_CONFORMITE)
    @action(detail=True, methods=['get'], url_path='conformite')
    def conformite(self, request, pk=None):
        """Rapport de conformité : qui a confirmé, quand, qui manque (admin)."""
        annonce = self.get_object()
        return Response(annonce_compliance_report(annonce))


class MessageAccueilViewSet(CompanyScopedModelViewSet):
    """MSGACC1 — message d'accueil posé par un responsable/admin pour UN
    employé, affiché en plein écran à sa PREMIÈRE ouverture de l'ERP à partir
    de ``visible_a_partir_de``. CE N'EST PAS UNE NOTIFICATION (voir la
    docstring du modèle) : aucun canal, aucun EventType.

    - ``a-lire`` (tout rôle) : mes messages dus et non lus (destinataire =
      moi), le plus ancien d'abord — c'est le SEUL endpoint que consomme la
      modale d'accueil.
    - ``lu`` (tout rôle, réservé au DESTINATAIRE) : idempotent.
    - Création : réservée au palier Responsable/Admin
      (``IsAdminOrResponsableTier``) ; ``company``/``auteur`` posés côté
      serveur.
    - ``list`` (écran de gestion) : mes messages envoyés, ou ceux de toute la
      société pour un Responsable/Admin.
    - Suppression : auteur ou Responsable/Admin, UNIQUEMENT si non lu.
    Aucune mise à jour (PUT/PATCH) : un message d'accueil s'envoie ou se
    supprime, il ne se corrige pas après coup."""
    queryset = MessageAccueil.objects.all()
    serializer_class = MessageAccueilSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload
    ANY_ROLE_ACTIONS = ['list', 'retrieve', 'a_lire', 'lu']

    def get_permissions(self):
        # Patron d'or (check_action_permission_override) : branchements
        # explicites par action, puis TOUJOURS le repli ``super()`` — jamais
        # une liste par défaut qui rendrait morte une permission déclarée.
        if self.action in self.ANY_ROLE_ACTIONS:
            return [IsAnyRole()]
        if self.action in ('create', 'destroy'):
            return [IsAdminOrResponsableTier()]
        return super().get_permissions()

    def _est_admin_ou_responsable(self, request):
        return IsAdminOrResponsableTier().has_permission(request, self)

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'a_lire':
            now = timezone.now()
            return qs.filter(
                destinataire=self.request.user,
                visible_a_partir_de__lte=now,
                lu_le__isnull=True,
            )
        if self.action == 'lu':
            # Réservé au destinataire : jamais l'auteur ni un admin ne
            # peuvent poser `lu_le` à la place de l'intéressé.
            return qs.filter(destinataire=self.request.user)
        if self._est_admin_ou_responsable(self.request):
            # Écran de gestion — un Responsable/Admin voit toute la société.
            return qs
        return qs.filter(auteur=self.request.user)

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, auteur=self.request.user)

    @extend_schema(responses=inline_serializer('MessagesAccueilALire', {
        'messages': inline_serializer('MessageAccueilALire', {
            'id': serializers.IntegerField(),
            'auteur_nom': serializers.CharField(allow_null=True),
            'visible_a_partir_de': serializers.DateTimeField(),
            'corps': serializers.CharField(),
        }, many=True),
    }))
    @action(detail=False, methods=['get'], url_path='a-lire')
    def a_lire(self, request):
        messages = [
            {
                'id': m.id,
                'auteur_nom': m.auteur.username if m.auteur_id else None,
                'visible_a_partir_de': m.visible_a_partir_de,
                'corps': m.corps,
            }
            for m in self.get_queryset().order_by('visible_a_partir_de', 'id')
        ]
        return Response({'messages': messages})

    @extend_schema(request=None, responses=MessageAccueilSerializer)
    @action(detail=True, methods=['post'], url_path='lu')
    def lu(self, request, pk=None):
        message = self.get_object()
        if message.lu_le is None:
            message.lu_le = timezone.now()
            message.save(update_fields=['lu_le'])
        return Response(self.get_serializer(message).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        est_admin = self._est_admin_ou_responsable(request)
        if instance.auteur_id != request.user.id and not est_admin:
            return Response(
                {'detail': "Réservé à l'auteur ou à un responsable/admin."},
                status=status.HTTP_403_FORBIDDEN)
        if instance.lu_le is not None:
            return Response(
                {'detail': 'Ce message a déjà été lu — suppression impossible.'},
                status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# FG5 — Endpoint de vérification des helpers de calendrier.

@extend_schema(
    parameters=[_q('date', OpenApiTypes.DATE,
                   "Date AAAA-MM-JJ (défaut : aujourd'hui).")],
    responses=inline_serializer('CalendrierOuvre', {
        'date': serializers.DateField(),
        'is_jour_ouvre': serializers.BooleanField(),
        'prochain_jour_ouvre': serializers.DateField(),
    }))
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

@extend_schema(responses={
    200: inline_serializer('CleVapid', {'public_key': serializers.CharField()}),
    403: _DETAIL,  # politique réseau de la société (middleware)
})
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def vapid_public_key(request):
    """Clé publique VAPID pour l'abonnement côté navigateur.

    Publique par nature. Chaîne vide tant que rien n'est configuré → le front
    sait alors que le push n'est pas disponible (NO-OP). Avec l'auto-génération
    (N109), renvoie la clé publique du singleton VAPID si aucune clé d'env."""
    return Response({'public_key': resolve_vapid_keys()[0]})


_NON_VIDE = r'\S'
_PUSH_SUBSCRIBE = inline_serializer('PushSubscribeRequest', {
    'endpoint': serializers.RegexField(_NON_VIDE),
    'keys': inline_serializer('PushSubscribeKeys', {
        'p256dh': serializers.RegexField(_NON_VIDE),
        'auth': serializers.RegexField(_NON_VIDE),
    }),
})


@extend_schema(request=_PUSH_SUBSCRIBE, responses={
    201: inline_serializer('PushSubscribed', {'id': serializers.IntegerField()}),
})
@api_view(['POST'])
@permission_classes([IsAnyRole])
@parser_classes([JSONParser])  # ENF8 (D2) — aucun upload
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


@extend_schema(responses=inline_serializer('AttentionSummary', {
    'actions_dues': serializers.IntegerField(),
    'en_retard': serializers.IntegerField(),
    'aujourdhui': serializers.IntegerField(),
    'approbations': serializers.IntegerField(),
    'mentions_non_lues': serializers.IntegerField(),
}))
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


@extend_schema(
    request=inline_serializer('PushUnsubscribeRequest', {
        'endpoint': serializers.RegexField(r'\S'),
    }),
    responses=inline_serializer(
        'PushUnsubscribed', {'deleted': serializers.IntegerField()}))
@api_view(['POST'])
@permission_classes([IsAnyRole])
@parser_classes([JSONParser])  # ENF8 (D2) — aucun upload
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
