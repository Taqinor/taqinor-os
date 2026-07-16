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
from core.api_usage import plan_pour_societe

from .models import ApiKey, Webhook, WebhookDelivery
from .serializers import (
    ApiKeySerializer, ApiKeyCreateSerializer, WebhookSerializer,
    WebhookDeliverySerializer, ApiUsagePlanSerializer, scope_catalogue,
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


class DocsView(APIView):
    """FG105 — Référence STATIQUE (FR) de l'API publique.

    Endpoints, authentification, scopes, évènements et recette de vérification
    de signature HMAC. Aucune auto-génération (pas de Swagger/drf-spectacular) :
    la référence est construite à la main à partir de `constants.py`. Réservée
    au palier admin/responsable, comme le catalogue, car elle est consultée
    depuis l'écran Paramètres → API & Webhooks.
    """
    permission_classes = [IsAdminOrResponsableTier]

    def get(self, request):
        from .docs import public_api_reference
        return Response(public_api_reference())


class OcrToCrmView(APIView):
    """FG106 — passerelle « Créer un lead / brouillon de devis depuis ce document ».

    Reçoit les champs structurés extraits par l'OCR et crée, côté CRM/ventes, un
    lead brouillon (mode ``lead``) ou un lead + un devis brouillon (mode
    ``devis``). L'ÉCRITURE cross-app passe TOUJOURS par les services.py des apps
    cibles (crm.services / ventes.services), via import paresseux local — jamais
    par leurs models/views. La société vient toujours de l'utilisateur connecté.
    Réservée au palier admin/responsable (même portée que la validation OCR).
    """
    permission_classes = [IsAdminOrResponsableTier]

    def post(self, request):
        # Imports paresseux locaux : pas d'import des models/views des apps cibles.
        from apps.crm.services import create_draft_lead_from_ocr
        from apps.ventes.services import create_draft_devis_from_ocr

        company = request.user.company
        mode = (request.data.get('mode') or 'lead').strip().lower()
        fields = request.data.get('fields') or {}
        if not isinstance(fields, dict):
            return Response(
                {'detail': "Le champ « fields » doit être un objet."},
                status=status.HTTP_400_BAD_REQUEST)
        if mode not in ('lead', 'devis'):
            return Response(
                {'detail': "Mode invalide (attendu « lead » ou « devis »)."},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            lead = create_draft_lead_from_ocr(
                company=company, user=request.user, fields=fields)
            payload = {'mode': mode, 'lead_id': lead.id}
            if mode == 'devis':
                devis = create_draft_devis_from_ocr(
                    company=company, user=request.user, lead=lead, fields=fields)
                payload['devis_id'] = devis.id
                payload['devis_reference'] = devis.reference
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_201_CREATED)


class ApiUsagePlanView(APIView):
    """NTAPI7 — plan d'API nommé (gratuit/pro/entreprise) de la société.

    ``GET`` renvoie (en le créant avec les défauts du palier gratuit s'il
    n'existe pas encore) le plan de LA société de l'utilisateur connecté.
    ``PATCH`` met à jour ses quotas/palier — la société est TOUJOURS forcée
    depuis ``request.user.company``, jamais lue du corps de requête (aucune
    fuite/écriture inter-société possible)."""
    permission_classes = [IsAdminOrResponsableTier]

    def get(self, request):
        plan = plan_pour_societe(request.user.company)
        return Response(ApiUsagePlanSerializer(plan).data)

    def patch(self, request):
        plan = plan_pour_societe(request.user.company)
        serializer = ApiUsagePlanSerializer(
            plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()  # `company` déjà posée sur `plan` — jamais du corps.
        return Response(serializer.data)


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


class ServiceAccountViewSet(viewsets.ModelViewSet):
    """NTSEC24 — comptes de service (identités machine), Directeur only.

    Le jeton en clair n'est renvoyé QU'À la création et à la rotation. La
    société est forcée côté serveur. Révocation = ``actif=False`` (ou DELETE)."""

    from authentication.permissions import IsAdminRole as _IsAdminRole
    permission_classes = [_IsAdminRole]

    def get_serializer_class(self):
        from .serializers import ServiceAccountSerializer
        return ServiceAccountSerializer

    def get_queryset(self):
        from .models import ServiceAccount
        user = self.request.user
        qs = ServiceAccount.objects.all()
        if getattr(user, 'company_id', None):
            return qs.filter(company=user.company)
        return qs.none()

    def create(self, request, *args, **kwargs):
        from .models import ServiceAccount
        nom = (request.data.get('nom') or '').strip()
        if not nom:
            return Response(
                {'nom': ['Ce champ est requis.']},
                status=status.HTTP_400_BAD_REQUEST)
        scopes = request.data.get('scopes') or []
        expire_le = request.data.get('expire_le') or None
        instance, raw = ServiceAccount.issue(
            company=request.user.company, nom=nom, scopes=scopes,
            created_by=request.user, expire_le=expire_le)
        data = self.get_serializer(instance).data
        data['token'] = raw  # une seule fois, jamais re-stocké
        return _no_store(Response(data, status=status.HTTP_201_CREATED))

    def perform_update(self, serializer):
        # La société n'est jamais lue du corps ; on la force à l'existante.
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def rotate(self, request, pk=None):
        """Rotation du jeton : invalide l'ancien, renvoie le nouveau (1 fois)."""
        instance = self.get_object()
        raw = instance.rotate()
        return _no_store(Response({'token': raw}))

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Révoque le compte de service (``actif=False``)."""
        instance = self.get_object()
        instance.actif = False
        instance.save(update_fields=['actif'])
        return Response({'actif': False})
