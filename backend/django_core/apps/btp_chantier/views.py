"""Vues du vertical BTP/EPC (Groupe NTCON) — scopées société (TenantMixin) +
lecture/écriture fine-grainée (``WriteScopedPermissionMixin``)."""
from django.contrib.contenttypes.models import ContentType
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from core.permissions import WriteScopedPermissionMixin

from . import selectors, services
from .models import RFI, ReserveChantier
from .serializers import (
    ReserveChantierSerializer, RFISerializer, SignatureBtpSerializer,
)


def _client_ip(request):
    """IP client (preuve de signature) — pattern ``contrats.views._client_ip``."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '') or ''
    return ip[:45]


def _photos_pour(instance, phase=None):
    """Pièces jointes ``records.Attachment`` ciblant ``instance`` (app de
    fondation — import direct autorisé, pas de frontière cross-app)."""
    from apps.records.models import Attachment
    qs = Attachment.objects.filter(
        company=instance.company,
        content_type=ContentType.objects.get_for_model(instance.__class__),
        object_id=instance.pk,
    )
    if phase:
        qs = qs.filter(phase=phase)
    return qs


class ReserveChantierViewSet(
        WriteScopedPermissionMixin, TenantMixin, viewsets.ModelViewSet):
    """Réserves de chantier (punch-list géo-localisée sur plan) — NTCON1/2.

    Filtres liste : ``?lot=&statut=&gravite=&chantier=``. Actions
    ``lever/`` (photo « après » obligatoire + signature) et ``contester/``
    (réouvre une réserve levée avec motif) sont posées par ``services.py``.
    """
    queryset = ReserveChantier.objects.select_related(
        'chantier', 'responsable_leve', 'leve_par', 'created_by').all()
    serializer_class = ReserveChantierSerializer
    read_permission = 'btp_voir'
    write_permission = 'btp_gerer'

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        return selectors.reserves_filtrees(
            qs, lot=p.get('lot'), statut=p.get('statut'),
            gravite=p.get('gravite'), chantier_id=p.get('chantier'))

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)
        services.enregistrer_creation_reserve(
            serializer.instance, created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def photos(self, request, pk=None):
        """Photos avant/pendant/après de la réserve (``records.Attachment``)."""
        from apps.records.serializers import AttachmentSerializer
        reserve = self.get_object()
        return Response(
            AttachmentSerializer(_photos_pour(reserve), many=True).data)

    @action(detail=True, methods=['post'])
    def lever(self, request, pk=None):
        """NTCON2 — lève la réserve. Requiert une photo « après » existante
        (400 sinon) et un ``signataire_nom`` (loi 53-05, 400 sinon)."""
        reserve = self.get_object()
        signataire_nom = (request.data.get('signataire_nom') or '').strip()
        if not signataire_nom:
            return Response(
                {'detail': 'signataire_nom est requis (loi 53-05).'},
                status=status.HTTP_400_BAD_REQUEST)
        if not _photos_pour(reserve, phase='apres').exists():
            return Response(
                {'detail': (
                    'Une photo « après » (records.Attachment phase=apres) '
                    'est requise avant de lever la réserve.')},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            signature = services.lever_reserve(
                reserve, user=request.user, signature_nom=signataire_nom,
                ip_adresse=_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''))
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        reserve.refresh_from_db()
        return Response({
            'reserve': ReserveChantierSerializer(reserve).data,
            'signature': SignatureBtpSerializer(signature).data,
        })

    @action(detail=True, methods=['post'])
    def contester(self, request, pk=None):
        """NTCON2 — réouvre une réserve levée (statut → contestee + motif)."""
        reserve = self.get_object()
        motif = (request.data.get('motif') or '').strip()
        if not motif:
            return Response(
                {'detail': 'motif est requis pour contester.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            services.contester_reserve(reserve, user=request.user, motif=motif)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        reserve.refresh_from_db()
        return Response(ReserveChantierSerializer(reserve).data)


class RFIViewSet(WriteScopedPermissionMixin, TenantMixin, viewsets.ModelViewSet):
    """RFI (Request For Information) — NTCON3.

    Filtres liste : ``?chantier=&statut=``. Triée par échéance dépassée en
    premier (``RFI.Meta.ordering``). Actions ``repondre/`` et ``clore/``.
    """
    queryset = RFI.objects.select_related(
        'chantier', 'pose_par', 'destinataire_user').prefetch_related(
            'reponses').all()
    serializer_class = RFISerializer
    read_permission = 'btp_voir'
    write_permission = 'btp_gerer'

    def get_queryset(self):
        qs = super().get_queryset()
        p = self.request.query_params
        return selectors.rfi_filtres(
            qs, chantier_id=p.get('chantier'), statut=p.get('statut'))

    def perform_create(self, serializer):
        rfi = services.creer_rfi(
            company=self.request.user.company,
            chantier=serializer.validated_data['chantier'],
            pose_par=self.request.user,
            delai_jours=serializer.validated_data.get('delai_jours', 5),
            question=serializer.validated_data['question'],
            destinataire_texte=serializer.validated_data.get(
                'destinataire_texte', ''),
            destinataire_user=serializer.validated_data.get(
                'destinataire_user'),
            impact_cout=serializer.validated_data.get('impact_cout', False),
            impact_delai_jours=serializer.validated_data.get(
                'impact_delai_jours'),
        )
        serializer.instance = rfi

    @action(detail=True, methods=['post'])
    def repondre(self, request, pk=None):
        rfi = self.get_object()
        texte = (request.data.get('texte') or '').strip()
        if not texte:
            return Response(
                {'detail': 'texte est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            services.repondre_rfi(rfi, auteur=request.user, texte=texte)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        rfi.refresh_from_db()
        return Response(RFISerializer(rfi).data)

    @action(detail=True, methods=['post'])
    def clore(self, request, pk=None):
        rfi = self.get_object()
        try:
            services.clore_rfi(rfi, user=request.user)
        except services.TransitionInvalide as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        rfi.refresh_from_db()
        return Response(RFISerializer(rfi).data)
