from django.db import transaction  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from django.utils import timezone  # noqa: F401
from rest_framework import viewsets, status, filters  # noqa: F401
from rest_framework.decorators import action, api_view, permission_classes  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from apps.stock.services import (  # noqa: F401
    mouvement_type_sortie, record_stock_movement,
)
from ..models import (  # noqa: F401
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    Avoir, LigneAvoir, FollowupLevel, RelanceLog, EmailLog,
    NoteDebit,
)
from ..serializers import (  # noqa: F401
    DevisSerializer,
    DevisWriteSerializer,
    BonCommandeSerializer,
    LigneDevisSerializer,
    FactureSerializer,
    FactureWriteSerializer,
    LigneFactureSerializer,
    PaiementSerializer,
    AvoirSerializer,
    NoteDebitSerializer,
    RelanceLogSerializer,
    DevisActivitySerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)
from ..utils.references import create_with_reference  # noqa: F401
from ..utils.company_settings import create_numbered  # noqa: F401

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


from authentication.scoping import scope_queryset  # noqa: E402,F401


def _company_qs(qs, user):
    """Filter queryset to user's company. Superusers without company see all."""
    if user.company_id:
        return qs.filter(company=user.company)
    if user.is_superuser:
        return qs
    return qs.none()

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class AvoirViewSet(viewsets.ReadOnlyModelViewSet):
    """Avoirs (notes de crédit) : lecture pour tout rôle ; PDF pour
    Responsable/Admin ; annulation Admin. Création via la facture
    (creer-avoir), jamais directement."""
    queryset = Avoir.objects.select_related(
        'client', 'facture', 'created_by').prefetch_related('lignes').all()
    serializer_class = AvoirSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'facture__reference', 'client__nom']
    ordering_fields = ['date_emission', 'reference']
    ordering = ['-date_emission']

    def get_queryset(self):
        qs = _company_qs(super().get_queryset(), self.request.user)
        # Portée de visibilité (Feature F) — avoirs créés par soi / l'équipe.
        qs = scope_queryset(qs, self.request.user, ['created_by'])
        facture_id = self.request.query_params.get('facture')
        if facture_id:
            qs = qs.filter(facture_id=facture_id)
        return qs

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        if self.action == 'annuler':
            return [IsAdminRole()]
        return [IsResponsableOrAdmin()]

    @staticmethod
    def _guard_periode_verrouillee(document):
        """YLEDG3 — même garde que FactureViewSet (voir sa docstring) :
        refuse (400) une mutation d'un avoir daté dans une période comptable
        CLÔTURÉE. Compta absent/aucune période = no-op silencieux."""
        try:
            from apps.compta.services import verifier_facture_modifiable
        except Exception:  # noqa: BLE001 — compta absent = no-op
            return
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError
        try:
            verifier_facture_modifiable(document)
        except DjangoValidationError as exc:
            raise ValidationError({'detail': exc.messages[0]
                                   if exc.messages else str(exc)})

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        avoir = self.get_object()
        self._guard_periode_verrouillee(avoir)
        avoir.statut = Avoir.Statut.ANNULEE
        avoir.save(update_fields=['statut'])
        return Response(AvoirSerializer(avoir).data)

    @action(detail=True, methods=['get'], url_path='telecharger-pdf')
    def telecharger_pdf(self, request, pk=None):
        avoir = self.get_object()
        from ..utils.pdf import download_pdf, generate_avoir_pdf
        try:
            if not avoir.fichier_pdf:
                generate_avoir_pdf(avoir.id)
                avoir.refresh_from_db()
            pdf_bytes = download_pdf(avoir.fichier_pdf)
        except Exception:
            return Response({'detail': 'PDF indisponible.'},
                            status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        # QD2 — nom cohérent (société _ type _ client _ référence).
        from ..utils.filenames import document_filename
        filename = document_filename(
            'Avoir', avoir.reference,
            client=avoir.client if avoir.client_id else None,
            company=avoir.company)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"')
        return response


class NoteDebitViewSet(viewsets.ReadOnlyModelViewSet):
    """ZFAC4 — notes de débit : lecture pour tout rôle ; PDF pour
    Responsable/Admin. Création via la facture (creer-note-debit), jamais
    directement — même patron qu'``AvoirViewSet``."""
    queryset = NoteDebit.objects.select_related(
        'client', 'facture', 'created_by').prefetch_related('lignes').all()
    serializer_class = NoteDebitSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'facture__reference', 'client__nom']
    ordering_fields = ['date_emission', 'reference']
    ordering = ['-date_emission']

    def get_queryset(self):
        qs = _company_qs(super().get_queryset(), self.request.user)
        qs = scope_queryset(qs, self.request.user, ['created_by'])
        facture_id = self.request.query_params.get('facture')
        if facture_id:
            qs = qs.filter(facture_id=facture_id)
        return qs

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=True, methods=['get'], url_path='telecharger-pdf')
    def telecharger_pdf(self, request, pk=None):
        note_debit = self.get_object()
        from ..utils.pdf import download_pdf, generate_note_debit_pdf
        try:
            if not note_debit.fichier_pdf:
                generate_note_debit_pdf(note_debit.id)
                note_debit.refresh_from_db()
            pdf_bytes = download_pdf(note_debit.fichier_pdf)
        except Exception:
            return Response({'detail': 'PDF indisponible.'},
                            status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        from ..utils.filenames import document_filename
        filename = document_filename(
            'NoteDebit', note_debit.reference,
            client=note_debit.client if note_debit.client_id else None,
            company=note_debit.company)
        response['Content-Disposition'] = (
            f'inline; filename="{filename}"')
        return response
