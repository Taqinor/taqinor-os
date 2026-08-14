"""Vues (ViewSets) de l'app `apps.transport` — toutes scopées société via
`core.viewsets.CompanyScopedModelViewSet` (jamais un `ModelViewSet` nu,
SCA4)."""
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet
from apps.records.views import ChatterViewSetMixin

from . import services
from .models import (
    CoutFretReel, EtapeTransport, LigneOrdreTransport, OrdreTransport,
)
from .serializers import (
    CoutFretReelSerializer, EtapeTransportSerializer,
    LigneOrdreTransportSerializer, OrdreTransportSerializer,
)


def _check_same_company(request, **fields):
    """Refuse (400) toute FK référençant un objet d'une AUTRE société — une
    `PrimaryKeyRelatedField` DRF n'est, par défaut, PAS scopée société ; sans
    ce garde un id valide d'une autre société serait accepté (IDOR)."""
    company = request.user.company
    cid = getattr(company, 'id', None)
    for name, obj in fields.items():
        if obj is not None and getattr(obj, 'company_id', None) != cid:
            raise ValidationError({name: 'Référence inconnue pour cette société.'})


class OrdreTransportViewSet(ChatterViewSetMixin, CompanyScopedModelViewSet):
    """NTLOG1 — ordre de transport. Filtrable par `?statut=`. `numero` posé
    côté serveur à la création (`services.attribuer_numero`, anti-collision,
    ARC6). Le chatter générique (`chatter/historique`/`chatter/noter`,
    ``ChatterViewSetMixin``) porte l'historique NTLOG8 (statut de l'ordre ET
    de ses étapes — voir ``services.log_activite_ordre``)."""

    queryset = OrdreTransport.objects.select_related(
        'created_by').prefetch_related('lignes', 'etapes').all()
    serializer_class = OrdreTransportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        conducteur = data.get('conducteur')
        erreur = services.valider_mode_transport_champs(
            data.get('mode_transport', OrdreTransport.ModeTransport.AFFRETEMENT),
            flotte_actif_id=data.get('flotte_actif_id'),
            conducteur_id=getattr(conducteur, 'id', None),
            installations_transporteur_id=data.get('installations_transporteur_id'),
        )
        if erreur:
            raise ValidationError({'mode_transport': erreur})
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)
        services.attribuer_numero(serializer.instance)

    def perform_update(self, serializer):
        instance = serializer.instance
        data = serializer.validated_data
        mode_transport = data.get('mode_transport', instance.mode_transport)
        conducteur = data.get('conducteur', instance.conducteur)
        flotte_actif_id = data.get('flotte_actif_id', instance.flotte_actif_id)
        installations_transporteur_id = data.get(
            'installations_transporteur_id',
            instance.installations_transporteur_id)
        erreur = services.valider_mode_transport_champs(
            mode_transport,
            flotte_actif_id=flotte_actif_id,
            conducteur_id=getattr(conducteur, 'id', None),
            installations_transporteur_id=installations_transporteur_id,
        )
        if erreur:
            raise ValidationError({'mode_transport': erreur})
        super().perform_update(serializer)

    # ── NTLOG3 — lecture imbriquée des étapes ────────────────────────────
    @action(detail=True, methods=['get'], url_path='etapes')
    def etapes_action(self, request, pk=None):
        ordre = self.get_object()
        return Response(
            EtapeTransportSerializer(ordre.etapes.all(), many=True).data)

    # ── NTLOG7 — comparateur de coûts d'affrètement ──────────────────────
    @action(detail=True, methods=['get'], url_path='comparer-transporteurs')
    def comparer_transporteurs(self, request, pk=None):
        ordre = self.get_object()
        from . import selectors
        return Response(
            selectors.comparer_transporteurs(
                ordre.id, company=request.user.company))


class LigneOrdreTransportViewSet(CompanyScopedModelViewSet):
    """NTLOG2 — marchandises d'un ordre. Filtrable par `?ordre=`."""

    queryset = LigneOrdreTransport.objects.select_related('ordre').all()
    serializer_class = LigneOrdreTransportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ordre = self.request.query_params.get('ordre')
        if ordre:
            qs = qs.filter(ordre_id=ordre)
        return qs

    def perform_create(self, serializer):
        _check_same_company(
            self.request, ordre=serializer.validated_data.get('ordre'))
        serializer.save(company=self.request.user.company)


class EtapeTransportViewSet(CompanyScopedModelViewSet):
    """NTLOG3 — étapes enlèvement/transit/livraison. Filtrable par
    `?ordre=`. Toute écriture de `statut_etape` déclenche l'avancement
    automatique du statut de l'ordre parent
    (`services.apres_changement_statut_etape`)."""

    queryset = EtapeTransport.objects.select_related('ordre').all()
    serializer_class = EtapeTransportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ordre = self.request.query_params.get('ordre')
        if ordre:
            qs = qs.filter(ordre_id=ordre)
        return qs

    def perform_create(self, serializer):
        _check_same_company(
            self.request, ordre=serializer.validated_data.get('ordre'))
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        ancien_statut = serializer.instance.statut_etape
        super().perform_update(serializer)
        services.apres_changement_statut_etape(
            serializer.instance, ancien_statut, user=self.request.user)

    # ── NTLOG9 — preuve de livraison (POD), réutilise records.Attachment ──
    @action(detail=True, methods=['post'], url_path='livrer')
    def livrer(self, request, pk=None):
        """Exige AU MOINS une pièce jointe (`records.Attachment`, photo ou
        signature) déjà déposée sur cette étape avant de la clôturer
        « fait » — sinon 400."""
        etape = self.get_object()
        from apps.records.models import Attachment
        ct = ContentType.objects.get_for_model(EtapeTransport)
        a_une_piece = Attachment.objects.filter(
            content_type=ct, object_id=etape.id).exists()
        if not a_une_piece:
            return Response(
                {'detail': (
                    'Photo ou signature requise avant de clôturer la '
                    'livraison.')},
                status=status.HTTP_400_BAD_REQUEST)
        ancien_statut = etape.statut_etape
        etape.statut_etape = EtapeTransport.StatutEtape.FAIT
        etape.save(update_fields=['statut_etape'])
        services.apres_changement_statut_etape(
            etape, ancien_statut, user=request.user)
        return Response(EtapeTransportSerializer(etape).data)


class CoutFretReelViewSet(CompanyScopedModelViewSet):
    """NTLOG16 — coûts de fret réels. Filtrable par `?ordre_transport=`."""

    queryset = CoutFretReel.objects.select_related('ordre_transport').all()
    serializer_class = CoutFretReelSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        ordre = self.request.query_params.get('ordre_transport')
        if ordre:
            qs = qs.filter(ordre_transport_id=ordre)
        return qs

    def perform_create(self, serializer):
        _check_same_company(
            self.request,
            ordre_transport=serializer.validated_data.get('ordre_transport'))
        serializer.save(company=self.request.user.company)
