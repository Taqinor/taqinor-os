"""Vues de GESTION (écran Paramètres) — clés API & webhooks (N89).

Montées sous /api/django/publicapi/. Authentifiées par la session/JWT normaux
(auth DRF par défaut du projet), réservées au palier admin/responsable. La
société vient TOUJOURS de l'utilisateur connecté, jamais du corps de requête.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAdminOrResponsableTier

from .models import ApiKey, Webhook, WebhookDelivery
from .serializers import (
    ApiKeySerializer, ApiKeyCreateSerializer, WebhookSerializer,
    WebhookDeliverySerializer, scope_catalogue,
)
from . import delivery as delivery_service


def _no_store(response):
    """ERR89 — Empêche toute mise en cache d'une réponse révélant un secret
    une seule fois (clé API / secret webhook). Proxies & navigateurs ne doivent
    jamais en garder une copie."""
    response['Cache-Control'] = 'no-store'
    response['Pragma'] = 'no-cache'
    return response


class _CompanyScopedMixin:
    """Filtre toujours par la société de l'utilisateur connecté."""
    permission_classes = [IsAdminOrResponsableTier]

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)


class CatalogueView(APIView):
    """Catalogue des scopes & évènements pour peupler l'écran Paramètres."""
    permission_classes = [IsAdminOrResponsableTier]

    def get(self, request):
        return Response(scope_catalogue())


class ApiKeyViewSet(_CompanyScopedMixin, viewsets.ModelViewSet):
    """CRUD des clés API. La clé en clair n'est renvoyée qu'à la création.

    Une clé ne peut PAS être modifiée (pas de PUT/PATCH du secret) : on la
    révoque (désactive) ou on la supprime, et on en émet une nouvelle.
    """
    serializer_class = ApiKeySerializer
    queryset = ApiKey.objects.select_related('created_by').all()
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def create(self, request, *args, **kwargs):
        in_ser = ApiKeyCreateSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        instance, raw_key = ApiKey.issue(
            company=request.user.company,
            label=in_ser.validated_data['label'],
            scopes=in_ser.validated_data['scopes'],
            created_by=request.user,
        )
        data = ApiKeySerializer(instance).data
        # La clé en clair n'est disponible QUE dans cette réponse de création.
        data['key'] = raw_key
        return _no_store(Response(data, status=status.HTTP_201_CREATED))

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Désactive une clé (révocation réversible, sans suppression)."""
        instance = self.get_object()
        instance.enabled = False
        instance.save(update_fields=['enabled'])
        return Response(ApiKeySerializer(instance).data)


class WebhookViewSet(_CompanyScopedMixin, viewsets.ModelViewSet):
    """CRUD des webhooks. Le secret est généré côté serveur et renvoyé une
    seule fois (création/rotation)."""
    serializer_class = WebhookSerializer
    queryset = Webhook.objects.all()

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user,
            secret=Webhook.generate_secret(),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        data = serializer.data
        # Le secret en clair n'est disponible QU'ICI, à la création.
        data['secret'] = serializer.instance.secret
        headers = self.get_success_headers(serializer.data)
        return _no_store(
            Response(data, status=status.HTTP_201_CREATED, headers=headers))

    @action(detail=True, methods=['post'])
    def rotate_secret(self, request, pk=None):
        """Régénère le secret du webhook ; renvoie le nouveau une seule fois."""
        instance = self.get_object()
        instance.secret = Webhook.generate_secret()
        instance.save(update_fields=['secret'])
        data = WebhookSerializer(instance).data
        data['secret'] = instance.secret
        return _no_store(Response(data))

    @action(detail=True, methods=['get'])
    def deliveries(self, request, pk=None):
        """Liste des 50 dernières livraisons de ce webhook (historique/diagnostic)."""
        instance = self.get_object()
        qs = WebhookDelivery.objects.filter(
            webhook=instance, company=request.user.company
        ).order_by('-created_at')[:50]
        return Response(WebhookDeliverySerializer(qs, many=True).data)

    @action(
        detail=True, methods=['post'],
        url_path=r'deliveries/(?P<delivery_id>[0-9]+)/replay',
    )
    def delivery_replay(self, request, pk=None, delivery_id=None):
        """Rejoue une livraison existante en renvoyant le même payload.

        Crée un NOUVEL enregistrement WebhookDelivery — la livraison originale
        est conservée intacte. Toujours company-scoped : la livraison doit
        appartenir au même webhook ET à la même société que l'utilisateur
        connecté.
        """
        webhook = self.get_object()  # lève 404 si mauvaise société
        try:
            original = WebhookDelivery.objects.get(
                id=delivery_id,
                webhook=webhook,
                company=request.user.company,
            )
        except WebhookDelivery.DoesNotExist:
            return Response(
                {"detail": "Livraison introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Réutilise la fonction de livraison existante (signature HMAC incluse).
        delivery_service._deliver_one(webhook, original.event, original.payload)
        # Renvoie le dernier enregistrement créé pour ce webhook (la nouvelle tentative).
        new_delivery = (
            WebhookDelivery.objects.filter(webhook=webhook)
            .order_by('-created_at')
            .first()
        )
        return Response(
            WebhookDeliverySerializer(new_delivery).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='test')
    def test_ping(self, request, pk=None):
        """Envoie un évènement de test synthétique vers ce webhook.

        Crée une charge utile test (type « ping ») et la livre immédiatement.
        L'évènement n'est PAS dans la liste officielle — le label « test »
        identifie clairement les pings dans l'historique de livraison.
        Toujours company-scoped.
        """
        webhook = self.get_object()  # lève 404 si mauvaise société
        test_event = 'webhook.test'
        test_payload = {
            'event': test_event,
            'webhook_id': webhook.id,
            'message': "Ceci est un ping de test depuis Taqinor.",
        }
        delivery_service._deliver_one(webhook, test_event, test_payload)
        new_delivery = (
            WebhookDelivery.objects.filter(webhook=webhook, event=test_event)
            .order_by('-created_at')
            .first()
        )
        return Response(
            WebhookDeliverySerializer(new_delivery).data,
            status=status.HTTP_201_CREATED,
        )
