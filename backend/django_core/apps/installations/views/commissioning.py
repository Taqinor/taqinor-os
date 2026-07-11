"""CH3 — Vues de la fiche de recette IEC 62446-1 (mise en service structurée).

La fiche est first-class côté ``installations`` : elle remplace la saisie libre
(``mes_*``) tout en la laissant lisible. Une fiche PASSÉE est requise par le
gate « Mise en service » (CH2). Multi-tenant : la société est TOUJOURS posée
côté serveur (jamais lue du corps) ; le queryset est scopé à la société du
demandeur.
"""
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import CommissioningRecord, CommissioningIVReading
from ..serializers_commissioning import (
    CommissioningRecordSerializer, CommissioningIVReadingSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class CommissioningRecordViewSet(CompanyScopedModelViewSet):
    """CH3 — fiches de recette IEC 62446-1. Lecture tout rôle, écriture
    Responsable/Admin. Filtrable par ``?installation=<id>``."""
    queryset = CommissioningRecord.objects.select_related(
        'installation').prefetch_related('iv_readings').all()
    serializer_class = CommissioningRecordSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        installation = self.request.query_params.get('installation')
        if installation:
            qs = qs.filter(installation_id=installation)
        return qs

    def _check_installation_tenant(self, serializer):
        """Le chantier ciblé doit appartenir à la société du demandeur."""
        from rest_framework.exceptions import ValidationError
        inst = serializer.validated_data.get('installation')
        company = self.request.user.company
        if inst is not None and inst.company_id != getattr(company, 'id', None):
            raise ValidationError({'installation': 'Chantier inconnu.'})

    @staticmethod
    def _check_instrument_etalonnage(serializer):
        """XFSM12 — un instrument dont l'étalonnage FG80 est expiré est
        toujours signalé (`instrument_etalonnage_expire`), et REFUSÉ (400)
        AVANT toute écriture seulement si `INSTRUMENT_ETALONNAGE_BLOQUANT` est
        activé (défaut : avertissement non-bloquant). Vérifié sur un
        instrument NON PERSISTÉ pour ne jamais créer/modifier la fiche quand le
        mode strict refuse."""
        if not settings.INSTRUMENT_ETALONNAGE_BLOQUANT:
            return
        instrument_id = serializer.validated_data.get('instrument_id')
        if not instrument_id:
            return
        pk = (serializer.instance.pk
              if serializer.instance is not None else None)
        transient = CommissioningRecord(pk=pk, instrument_id=instrument_id)
        if transient.instrument_etalonnage_expire:
            raise ValidationError({
                'instrument_id': (
                    "L'étalonnage de cet instrument est expiré — "
                    "enregistrement bloqué (mode strict).")})

    def perform_create(self, serializer):
        self._check_installation_tenant(serializer)
        self._check_instrument_etalonnage(serializer)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_installation_tenant(serializer)
        self._check_instrument_etalonnage(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='ajouter-iv',
            permission_classes=[IsResponsableOrAdmin])
    def ajouter_iv(self, request, pk=None):
        """CH3/FG275 — ajoute un relevé I-V par string à la fiche ; l'écart de
        Pmax (mesuré vs attendu) et le drapeau de défaut sont calculés côté
        serveur."""
        from ..services import compute_iv_ecart
        record = self.get_object()
        serializer = CommissioningIVReadingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reading = CommissioningIVReading(
            record=record, company=record.company,
            **{k: v for k, v in serializer.validated_data.items()
               if k != 'record'})
        compute_iv_ecart(reading)
        reading.save()
        return Response(
            CommissioningIVReadingSerializer(reading).data,
            status=status.HTTP_201_CREATED)
