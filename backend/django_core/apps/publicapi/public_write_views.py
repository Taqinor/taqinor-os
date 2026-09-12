"""XPLT5 — API publique en ÉCRITURE (scopes `leads:write` / `activities:write`).

Authentifiée par clé d'API (comme les vues lecture seule), scopée à la société
de la clé (jamais du body), avec support de l'en-tête `Idempotency-Key`
(mémorisation par (clé, endpoint, clé d'idempotence) — un rejeu identique
renvoie la même réponse, un corps différent → 409). Les ÉCRITURES passent
TOUJOURS par `apps.crm.services` (jamais par ses models/views directement),
comme l'exige la frontière inter-app cross-domaine."""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.crm.models import Lead

from .auth import PUBLIC_AUTHENTICATION_CLASSES, ApiKeyRateThrottle
from .constants import (
    SCOPE_WRITE_ACTIVITIES, SCOPE_WRITE_DEVIS, SCOPE_WRITE_LEADS,
    SCOPE_WRITE_TICKETS,
)
from .idempotency import get_idempotency_key, replay_or_none, remember
from .public_response import PublicApiResponseMixin
from .public_serializers import PublicLeadSerializer


class PublicWriteAPIView(PublicApiResponseMixin, APIView):
    """Base commune : auth par clé d'API, throttle par clé, scope requis
    déclaré par la sous-classe (`required_scope`), idempotence optionnelle.

    ``permission_classes`` est explicitement ``[AllowAny]`` : le projet a pour
    permission DRF par défaut ``IsAuthenticated`` (qui exige un utilisateur de
    session) — or l'API publique authentifie par clé d'API, jamais par
    session (``ApiKeyUser.is_authenticated`` est toujours ``False``). Sans ce
    override, ``super().check_permissions`` rejetterait TOUJOURS avec 403,
    avant même que le contrôle de scope ci-dessous ne s'exécute. Le contrôle
    d'accès réel est le scope check explicite plus bas (parallèle à
    ``HasApiScope`` sur ``PublicReadOnlyViewSet`` côté lecture)."""
    authentication_classes = PUBLIC_AUTHENTICATION_CLASSES
    permission_classes = [AllowAny]
    throttle_classes = [ApiKeyRateThrottle]
    required_scope = None
    endpoint_name = None  # identifiant stable pour le scope d'idempotence

    def check_permissions(self, request):
        super().check_permissions(request)
        api_key = getattr(request, 'auth', None)
        if api_key is None:
            raise PermissionDenied("Authentification par clé API requise.")
        if not api_key.has_scope(self.required_scope):
            raise PermissionDenied(
                "Cette clé API n'a pas le droit nécessaire "
                f"({self.required_scope}).")

    def get_company(self):
        return self.request.auth.company

    def idempotent_post(self, request, *, body_for_fingerprint, perform):
        """Enveloppe commune : rejoue une réponse mémorisée si l'en-tête
        `Idempotency-Key` correspond à un appel identique déjà traité ;
        sinon exécute `perform()` (qui doit renvoyer un ``Response``) et
        mémorise le résultat pour un futur rejeu."""
        api_key = request.auth
        idem_key = get_idempotency_key(request)
        replay = replay_or_none(
            api_key=api_key, endpoint=self.endpoint_name,
            idem_key=idem_key, body=body_for_fingerprint)
        if replay is not None:
            resp_status, resp_body = replay
            return Response(resp_body, status=resp_status)

        response = perform()

        remember(
            company=self.get_company(), api_key=api_key,
            endpoint=self.endpoint_name, idem_key=idem_key,
            body=body_for_fingerprint,
            response_status=response.status_code, response_body=response.data,
        )
        return response


class PublicLeadCreateView(PublicWriteAPIView):
    """POST /api/public/v1/leads-write/ — crée un lead (scope `leads:write`)."""
    required_scope = SCOPE_WRITE_LEADS
    endpoint_name = 'leads-write:create'

    def post(self, request):
        from apps.crm.services import create_lead_from_public_api

        def _perform():
            try:
                lead = create_lead_from_public_api(
                    company=self.get_company(), fields=request.data or {})
            except ValueError as exc:
                raise ValidationError({'detail': str(exc)})
            data = PublicLeadSerializer(lead).data
            return Response(data, status=status.HTTP_201_CREATED)

        return self.idempotent_post(
            request, body_for_fingerprint=request.data, perform=_perform)


class PublicLeadUpdateView(PublicWriteAPIView):
    """PATCH /api/public/v1/leads-write/<id>/ — met à jour un lead DE CETTE
    SOCIÉTÉ (scope `leads:write`). 404 si le lead n'appartient pas à la
    société de la clé (jamais de fuite cross-tenant)."""
    required_scope = SCOPE_WRITE_LEADS
    endpoint_name = 'leads-write:update'

    def patch(self, request, pk=None):
        from apps.crm.services import update_lead_from_public_api

        def _perform():
            try:
                lead = update_lead_from_public_api(
                    company=self.get_company(), lead_id=pk,
                    fields=request.data or {})
            except Lead.DoesNotExist:
                return Response(
                    {'detail': 'Lead introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            except ValueError as exc:
                raise ValidationError({'detail': str(exc)})
            data = PublicLeadSerializer(lead).data
            return Response(data, status=status.HTTP_200_OK)

        return self.idempotent_post(
            request, body_for_fingerprint={'pk': pk, **(request.data or {})},
            perform=_perform)


class PublicActivityCreateView(PublicWriteAPIView):
    """POST /api/public/v1/leads-write/<id>/activites/ — ajoute une note chatter
    sur un lead DE CETTE SOCIÉTÉ (scope `activities:write`)."""
    required_scope = SCOPE_WRITE_ACTIVITIES
    endpoint_name = 'activities-write:create'

    def post(self, request, pk=None):
        from apps.crm.services import create_activity_from_public_api

        def _perform():
            try:
                act = create_activity_from_public_api(
                    company=self.get_company(), lead_id=pk,
                    body=(request.data or {}).get('body'))
            except Lead.DoesNotExist:
                return Response(
                    {'detail': 'Lead introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            except ValueError as exc:
                raise ValidationError({'detail': str(exc)})
            return Response(
                {'id': act.id, 'body': act.body,
                 'created_at': act.created_at.isoformat()},
                status=status.HTTP_201_CREATED)

        return self.idempotent_post(
            request, body_for_fingerprint={'pk': pk, **(request.data or {})},
            perform=_perform)


class PublicDevisCreateView(PublicWriteAPIView):
    """NTAPI18 — ``POST /api/public/v1/devis-write/`` : crée un devis
    BROUILLON rattaché à un lead existant (scope ``devis:write``).

    Corps : ``{"lead": <id>}`` (obligatoire — le client est résolu SERVEUR
    depuis le lead par ``crm.services.resolve_client_for_lead``, jamais
    dupliqué), plus les champs d'aide à la saisie optionnels
    (``numero``/``montant_ht``/``montant_tva``/``montant_ttc``/``date``),
    consignés en note.

    CE QUE CET ENDPOINT NE FAIT JAMAIS : créer des lignes (une ``LigneDevis``
    exige un produit du catalogue, qu'un appel d'intégration ne fournit pas),
    ni changer un statut aval (règle #4 — le devis reste ``brouillon``, et
    l'unique chemin du PDF client demeure ``/proposal``). L'écriture passe
    EXCLUSIVEMENT par ``ventes.services`` et le lead est lu par
    ``crm.selectors`` — jamais un import de models cross-app."""
    required_scope = SCOPE_WRITE_DEVIS
    endpoint_name = 'devis-write:create'

    @extend_schema(
        request=inline_serializer('PublicDevisCreateRequete', {
            'lead': drf_serializers.IntegerField(),
            'numero': drf_serializers.CharField(required=False),
            'montant_ht': drf_serializers.CharField(required=False),
            'montant_tva': drf_serializers.CharField(required=False),
            'montant_ttc': drf_serializers.CharField(required=False),
            'date': drf_serializers.CharField(required=False),
        }),
        responses={201: inline_serializer('PublicDevisCreateReponse', {
            'id': drf_serializers.IntegerField(),
            'reference': drf_serializers.CharField(),
            'statut': drf_serializers.CharField(),
            'lead': drf_serializers.IntegerField(),
            'client': drf_serializers.IntegerField(),
        })})
    def post(self, request):
        from apps.crm.selectors import get_company_lead
        from apps.ventes.services import create_draft_devis_from_ocr

        def _perform():
            corps = request.data or {}
            lead_id = corps.get('lead')
            if not lead_id:
                raise ValidationError(
                    {'lead': "Le champ « lead » est obligatoire."})
            # Société FORCÉE depuis la clé : un id d'une autre société renvoie
            # None ici, donc 404 — jamais de fuite ni d'écriture cross-tenant.
            lead = get_company_lead(self.get_company(), lead_id)
            if lead is None:
                return Response(
                    {'detail': 'Lead introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            try:
                devis = create_draft_devis_from_ocr(
                    company=self.get_company(),
                    # Aucun utilisateur humain derrière une clé d'API :
                    # `created_by` reste NULL plutôt que d'attribuer le devis
                    # à quelqu'un qui ne l'a pas créé.
                    user=None,
                    lead=lead,
                    fields=corps,
                    origine=(
                        "Devis brouillon créé via l'API publique "
                        "(intégration externe)."),
                )
            except ValueError as exc:
                raise ValidationError({'detail': str(exc)})
            return Response(
                {'id': devis.id, 'reference': devis.reference,
                 'statut': devis.statut, 'lead': devis.lead_id,
                 'client': devis.client_id},
                status=status.HTTP_201_CREATED)

        return self.idempotent_post(
            request, body_for_fingerprint=request.data, perform=_perform)


class PublicTicketCreateView(PublicWriteAPIView):
    """NTAPI18 — ``POST /api/public/v1/tickets-write/`` : ouvre un ticket SAV
    correctif (scope ``tickets:write``).

    Corps : ``{"client": <id>, "description": "...", "installation": <id>?}``.
    ``installation`` est optionnelle (un ticket peut ne viser aucun chantier
    précis) mais, quand elle est fournie, elle est elle aussi bornée à la
    société de la clé. L'écriture passe par ``sav.services`` et les entités
    liées sont lues par les ``selectors`` de leurs apps — jamais un import de
    models cross-app."""
    required_scope = SCOPE_WRITE_TICKETS
    endpoint_name = 'tickets-write:create'

    @extend_schema(
        request=inline_serializer('PublicTicketCreateRequete', {
            'client': drf_serializers.IntegerField(),
            'description': drf_serializers.CharField(),
            'installation': drf_serializers.IntegerField(required=False),
        }),
        responses={201: inline_serializer('PublicTicketCreateReponse', {
            'id': drf_serializers.IntegerField(),
            'reference': drf_serializers.CharField(),
            'statut': drf_serializers.CharField(),
            'client': drf_serializers.IntegerField(),
            'installation': drf_serializers.IntegerField(allow_null=True),
        })})
    def post(self, request):
        from apps.crm.selectors import get_company_client
        from apps.installations.selectors import installation_scoped
        from apps.sav.services import create_corrective_ticket

        def _perform():
            corps = request.data or {}
            description = (corps.get('description') or '').strip()
            if not description:
                raise ValidationError(
                    {'description': "Le champ « description » est obligatoire."})
            client = get_company_client(self.get_company(), corps.get('client'))
            if client is None:
                return Response(
                    {'detail': 'Client introuvable.'},
                    status=status.HTTP_404_NOT_FOUND)
            installation = None
            if corps.get('installation'):
                installation = installation_scoped(
                    self.get_company(), corps.get('installation'))
                if installation is None:
                    return Response(
                        {'detail': 'Chantier introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
            try:
                ticket = create_corrective_ticket(
                    company=self.get_company(),
                    client=client,
                    installation=installation,
                    description=description,
                    # Aucun utilisateur humain derrière une clé d'API.
                    created_by=None,
                )
            except ValueError as exc:
                raise ValidationError({'detail': str(exc)})
            return Response(
                {'id': ticket.id, 'reference': ticket.reference,
                 'statut': ticket.statut, 'client': ticket.client_id,
                 'installation': ticket.installation_id},
                status=status.HTTP_201_CREATED)

        return self.idempotent_post(
            request, body_for_fingerprint=request.data, perform=_perform)
