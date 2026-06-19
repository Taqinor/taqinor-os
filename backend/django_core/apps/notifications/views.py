"""N75 — API des notifications, strictement par utilisateur.

TenantMixin scope déjà par société ; on RESTREINT en plus au destinataire
courant pour que personne ne voie les notifications d'autrui. La société ET le
destinataire/utilisateur sont posés côté serveur, jamais lus du corps.
"""
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole

from .models import EventType, Notification, NotificationPreference
from .serializers import (
    NotificationPreferenceSerializer, NotificationSerializer,
)
from .services import merged_preferences


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
