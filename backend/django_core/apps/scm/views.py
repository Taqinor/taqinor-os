"""Vues de planification supply chain (Groupe NTSCM).

Accès réservé Responsable/Administrateur (données de planification achat —
même palier que les modules de conformité/planification voisins, ex.
``apps.fiscal``) : ``get_permissions`` renvoie ``[IsResponsableOrAdmin()]``
sur chaque viewset, société toujours scopée par ``CompanyScopedModelViewSet``.
"""
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import EvenementDemande, PrevisionDemande
from .serializers import EvenementDemandeSerializer, PrevisionDemandeSerializer


class PrevisionDemandeViewSet(CompanyScopedModelViewSet):
    """CRUD des prévisions de demande (NTSCM1) + génération automatique
    (NTSCM2/3, ``@action`` ``generer``)."""
    queryset = PrevisionDemande.objects.select_related(
        'produit', 'genere_par').all()
    serializer_class = PrevisionDemandeSerializer
    filterset_fields = ['produit', 'segment']

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        periode_min = self.request.query_params.get('periode_min')
        periode_max = self.request.query_params.get('periode_max')
        if periode_min:
            qs = qs.filter(periode__gte=periode_min)
        if periode_max:
            qs = qs.filter(periode__lte=periode_max)
        return qs

    @action(detail=False, methods=['post'], url_path='generer')
    def generer(self, request):
        """NTSCM2/3 — (re)génère les prévisions d'un produit sur un horizon
        donné. Corps : ``{"produit_id": …, "horizon_mois": 3, "segment": ""}``.
        Le produit est résolu via ``apps.stock.selectors`` (jamais un import
        de modèle)."""
        from apps.stock.selectors import get_produit_scoped

        from . import services

        produit_id = request.data.get('produit_id')
        if not produit_id:
            return Response({'produit_id': 'Requis.'}, status=400)
        produit = get_produit_scoped(request.user.company, produit_id)
        if produit is None:
            return Response({'produit_id': 'Produit introuvable.'}, status=404)

        horizon_mois = int(request.data.get('horizon_mois') or 3)
        segment = request.data.get('segment') or ''
        previsions = services.generer_previsions(
            produit, horizon_mois, request.user.company,
            segment=segment, user=request.user)
        return Response(
            PrevisionDemandeSerializer(previsions, many=True).data)


class EvenementDemandeViewSet(CompanyScopedModelViewSet):
    """CRUD des événements de demande (NTSCM3) — promotions, chantiers
    planifiés, ruptures fournisseur connues, appliqués par
    ``services.generer_previsions``."""
    queryset = EvenementDemande.objects.select_related(
        'produit', 'categorie').all()
    serializer_class = EvenementDemandeSerializer
    filterset_fields = ['produit', 'categorie', 'type_evenement']

    def get_permissions(self):
        return [IsResponsableOrAdmin()]
