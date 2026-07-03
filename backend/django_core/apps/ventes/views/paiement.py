from django.db import transaction  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from django.utils import timezone  # noqa: F401
from rest_framework import viewsets, status, filters  # noqa: F401
from rest_framework.decorators import action, api_view, permission_classes  # noqa: F401
from rest_framework.exceptions import ValidationError  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from apps.stock.services import (  # noqa: F401
    mouvement_type_sortie, record_stock_movement,
)
from ..models import (  # noqa: F401
    Devis, LigneDevis, BonCommande, Facture, LigneFacture, Paiement,
    AffectationPaiement, Avoir, LigneAvoir, FollowupLevel, RelanceLog,
    EmailLog,
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
    AffectationPaiementSerializer,
    AvoirSerializer,
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


class PaiementViewSet(viewsets.ReadOnlyModelViewSet):
    """Lecture seule des paiements (l'enregistrement passe par la facture) —
    XFAC1 ajoute deux actions d'écriture pour les AVANCES non affectées
    (règlement reçu sans facture) : enregistrement + ventilation sur des
    factures ouvertes du même client.

    Visible par tout rôle authentifié ; tenant-scopé par société.
    """
    queryset = Paiement.objects.select_related(
        'facture', 'facture__client', 'client', 'created_by'
    ).all()
    serializer_class = PaiementSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_paiement', 'montant', 'date_creation']
    ordering = ['-date_paiement']

    def get_queryset(self):
        return _company_qs(super().get_queryset(), self.request.user)

    def get_permissions(self):
        if self.action in ('enregistrer_avance', 'ventiler'):
            return [IsResponsableOrAdmin()]
        return [IsAnyRole()]

    @action(detail=False, methods=['get'], url_path='avances-non-affectees')
    def avances_non_affectees(self, request):
        """XFAC1 — avances (paiements sans facture) encore disponibles,
        optionnellement filtrées par client (``?client=<id>``)."""
        qs = self.get_queryset().filter(
            facture__isnull=True,
        ).exclude(
            statut_affectation=Paiement.StatutAffectation.AFFECTE)
        client_id = request.query_params.get('client')
        if client_id:
            qs = qs.filter(client_id=client_id)
        rows = [p for p in qs if p.montant_disponible > 0]
        return Response(PaiementSerializer(rows, many=True).data)

    @action(detail=False, methods=['post'], url_path='enregistrer-avance')
    def enregistrer_avance(self, request):
        """XFAC1 — enregistre un règlement reçu SANS facture (avance/acompte à
        la commande/trop-perçu), rattaché directement au client."""
        from apps.crm.selectors import client_base_qs
        from ..services import enregistrer_avance as _enregistrer_avance

        company = request.user.company
        client_id = request.data.get('client')
        client = _company_qs(client_base_qs(), request.user).filter(
            pk=client_id).first()
        if client is None:
            return Response({'detail': 'Client introuvable.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            paiement = _enregistrer_avance(
                company=company, client=client,
                montant=request.data.get('montant'),
                date_paiement=request.data.get('date_paiement'),
                mode=request.data.get('mode', Paiement.Mode.VIREMENT),
                reference=request.data.get('reference', ''),
                note=request.data.get('note', ''),
                created_by=request.user,
            )
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PaiementSerializer(paiement).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='ventiler')
    def ventiler(self, request, pk=None):
        """XFAC1 — ventile une avance non affectée sur UNE facture ouverte du
        même client. Corps : ``{facture, montant}``. Peut être appelée
        plusieurs fois pour répartir la même avance sur plusieurs factures."""
        from ..services import ventiler_avance as _ventiler_avance

        paiement = self.get_object()
        facture = _company_qs(Facture.objects.all(), request.user).filter(
            pk=request.data.get('facture')).first()
        if facture is None:
            return Response({'detail': 'Facture introuvable.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            affectation = _ventiler_avance(
                paiement=paiement, facture=facture,
                montant=request.data.get('montant'), user=request.user,
            )
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            AffectationPaiementSerializer(affectation).data,
            status=status.HTTP_201_CREATED)
