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
    EventType, Notification, NotificationPreference, NotificationRoutingRule,
    PushSubscription,
)
from .serializers import (
    NotificationPreferenceSerializer, NotificationRoutingRuleSerializer,
    NotificationSerializer,
)
from .services import merged_preferences, resolve_vapid_keys


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
        count = self.get_queryset().filter(read=False).count()
        return Response({'unread': count})

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
        now = timezone.now()
        updated = self.get_queryset().filter(read=False).update(
            read=True, read_at=now)
        return Response({'updated': updated})


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
