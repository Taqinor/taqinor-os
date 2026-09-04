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
        """YLEDG3 — même garde que FactureViewSet : refuse (400) une mutation
        d'un avoir daté dans une période comptable CLÔTURÉE. AUD122 — la
        copie locale a laissé place à la fonction PARTAGÉE
        ``utils.periode.guard_periode_verrouillee`` (comportement identique,
        no-op silencieux si compta est absente)."""
        from ..utils.periode import guard_periode_verrouillee
        guard_periode_verrouillee(document)

    @staticmethod
    def _trace_contre_passation(avoir):
        """AUD127 — retrouve la trace ZFAC5 qui a annulé la facture d'origine
        POUR CET AVOIR.

        Un avoir de contre-passation ne porte pas son mode : la seule preuve
        du lien est le ``FactureActivity`` posé par ``creer_avoir``, dont le
        corps nomme l'avoir miroir et dont ``old_value`` porte le statut que
        la facture avait AVANT d'être annulée. C'est exactement ce qu'il faut
        pour la restaurer.
        """
        from ..models import FactureActivity
        if avoir.facture_id is None:
            return None
        return (FactureActivity.objects
                .filter(facture_id=avoir.facture_id, field='statut',
                        new_value=Facture.Statut.ANNULEE,
                        body__contains=f'avoir miroir {avoir.reference}')
                .order_by('-id')
                .first())

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """AUD127 — annule un avoir ET contre-passe son effet.

        L'action posait ``statut='annulee'`` et rendait la réponse : AUCUN
        événement, alors que la CRÉATION émet ``avoir_cree`` auquel compta
        abonne l'écriture d'avoir. L'effet ERP était immédiat —
        ``Facture.avoirs_total`` exclut les avoirs annulés, donc
        ``montant_du`` remonte — pendant que le grand livre gardait l'avoir :
        une créance de 20 000 réapparaissait côté ERP alors que la
        comptabilité la considérait toujours comme créditée. Et si l'avoir
        était une CONTRE-PASSATION, la facture d'origine avait été forcée à
        ANNULEE et rien ne la restaurait.

        Désormais : idempotente (double annulation = no-op), elle restaure la
        facture d'origine d'une contre-passation à son statut antérieur (ou
        refuse en 400 si ce statut est introuvable), et émet ``avoir_annule``
        exactement une fois — d'où l'extourne côté compta.
        """
        avoir = self.get_object()
        if avoir.statut == Avoir.Statut.ANNULEE:
            # Idempotence : rien à annuler, aucun événement ré-émis (une
            # seconde extourne doublerait le grand livre).
            return Response(AvoirSerializer(avoir).data)
        self._guard_periode_verrouillee(avoir)

        from core.events import avoir_annule

        with transaction.atomic():
            trace = self._trace_contre_passation(avoir)
            if trace is not None:
                facture = Facture.objects.select_for_update().get(
                    pk=avoir.facture_id)
                ancien = (trace.old_value or '').strip()
                if not ancien or ancien == Facture.Statut.ANNULEE:
                    return Response(
                        {'detail': (
                            "Annulation refusée : cet avoir a contre-passé la "
                            f"facture {facture.reference}, et son statut "
                            "antérieur est introuvable — la facture ne peut "
                            "pas être restaurée."
                        )},
                        status=status.HTTP_400_BAD_REQUEST)
                if facture.statut == Facture.Statut.ANNULEE:
                    facture.statut = ancien
                    facture.save(update_fields=['statut'])
                    from ..models import FactureActivity
                    FactureActivity.objects.create(
                        company=facture.company, facture=facture,
                        user=request.user,
                        kind=FactureActivity.Kind.MODIFICATION,
                        field='statut', field_label='Statut',
                        old_value=Facture.Statut.ANNULEE, new_value=ancien,
                        body=(f"Facture restaurée : l'avoir de "
                              f"contre-passation {avoir.reference} a été "
                              f"annulé."),
                    )
            avoir.statut = Avoir.Statut.ANNULEE
            avoir.save(update_fields=['statut'])
            # YLEDG4 — symétrique d'``avoir_cree`` : compta extourne
            # l'écriture d'avoir (jamais de suppression, COMPTA11).
            avoir_annule.send(
                sender=Avoir, instance=avoir, company=avoir.company)
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
