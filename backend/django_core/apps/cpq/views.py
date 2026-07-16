"""Vues (API) de l'app CPQ.

Tous les ViewSets héritent de ``CompanyScopedModelViewSet`` (ARC2) : le
queryset est scopé société et ``perform_create`` force ``company`` côté
serveur. La liste des produits n'est jamais lue du corps pour le scope."""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.viewsets import CompanyScopedModelViewSet
from authentication.permissions import IsResponsableOrAdmin, IsAnyRole

from .models import (
    OptionProduit, ContrainteCompatibilite, RegleProduitCPQ, OffreGroupee,
    PrixContractuel,
)
from .serializers import (
    OptionProduitSerializer, ContrainteCompatibiliteSerializer,
    RegleProduitCPQSerializer, OffreGroupeeSerializer,
    PrixContractuelSerializer,
)
from . import selectors, services


class OptionProduitViewSet(CompanyScopedModelViewSet):
    queryset = OptionProduit.objects.all()
    serializer_class = OptionProduitSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class ContrainteCompatibiliteViewSet(CompanyScopedModelViewSet):
    queryset = ContrainteCompatibilite.objects.all()
    serializer_class = ContrainteCompatibiliteSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class RegleProduitCPQViewSet(CompanyScopedModelViewSet):
    queryset = RegleProduitCPQ.objects.all()
    serializer_class = RegleProduitCPQSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'evaluer'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=False, methods=['post'], url_path='evaluer')
    def evaluer(self, request):
        """NTCPQ2 — Évalue les règles actives contre un contexte fourni.

        Corps : ``{"context": {...}}`` (dict plat construit depuis les lignes
        candidates du devis, ex. ``{"kwc": 12}``). Renvoie les actions
        déclenchées."""
        context = request.data.get('context')
        if context is None:
            # Repli : tout champ hors "context" est traité comme le contexte.
            context = {k: v for k, v in request.data.items() if k != 'context'}
        declenchees = selectors.evaluer_regles_produit(
            company=request.user.company, context=context)
        return Response({'actions_declenchees': declenchees})


class OffreGroupeeViewSet(CompanyScopedModelViewSet):
    queryset = OffreGroupee.objects.prefetch_related('lignes').all()
    serializer_class = OffreGroupeeSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    @action(detail=True, methods=['post'], url_path='appliquer',
            permission_classes=[IsResponsableOrAdmin])
    def appliquer(self, request, pk=None):
        """NTCPQ3 — Applique le bundle au devis ``?devis_id=`` : insère les
        LigneDevis correspondantes en respectant le mode de prix."""
        offre = self.get_object()
        devis_id = request.query_params.get('devis_id') or request.data.get('devis_id')
        if not devis_id:
            return Response({'detail': 'devis_id requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        from apps.ventes.models import Devis
        try:
            devis = Devis.objects.get(pk=devis_id, company=request.user.company)
        except Devis.DoesNotExist:
            return Response({'detail': 'Devis introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        lignes = services.appliquer_offre_groupee(
            offre=offre, devis=devis, user=request.user)
        return Response({
            'detail': f'Offre « {offre.nom} » appliquée.',
            'lignes_creees': [li.id for li in lignes],
            'sous_total_ht': str(devis.total_ht),
        }, status=status.HTTP_201_CREATED)


class PrixContractuelViewSet(CompanyScopedModelViewSet):
    queryset = PrixContractuel.objects.select_related(
        'client', 'produit').all()
    serializer_class = PrixContractuelSerializer
    # NTCPQ5 — CRUD réservé Directeur / Commercial responsable.
    permission_classes = [IsResponsableOrAdmin]

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        company = self.request.user.company
        client = serializer.validated_data.get('client')
        produit = serializer.validated_data.get('produit')
        if client is not None and client.company_id != company.id:
            raise ValidationError({'client': 'Client inconnu.'})
        if produit is not None and produit.company_id != company.id:
            raise ValidationError({'produit': 'Produit inconnu.'})
        serializer.save(company=company, created_by=self.request.user)


class ValiderCompatibiliteView(APIView):
    """NTCPQ1 — POST cpq/valider-compatibilite/.

    Corps : ``{"produit_ids": [1, 2, 3]}``. Renvoie les violations, séparées en
    ``bloquantes`` (INCOMPATIBLE / REQUIERT) et ``avertissements`` (RECOMMANDE)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        company = request.user.company
        produit_ids = request.data.get('produit_ids') or []
        if not isinstance(produit_ids, (list, tuple)):
            return Response(
                {'detail': 'produit_ids doit être une liste.'},
                status=status.HTTP_400_BAD_REQUEST)
        violations = selectors.violations_compatibilite(
            company=company, produit_ids=produit_ids)
        bloquantes = [v for v in violations if v['bloquante']]
        avertissements = [v for v in violations if not v['bloquante']]
        return Response({
            'valide': not bloquantes,
            'violations': violations,
            'bloquantes': bloquantes,
            'avertissements': avertissements,
        })
