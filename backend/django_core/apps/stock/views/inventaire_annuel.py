from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from ..models import InventaireAnnuel
from ..serializers import InventaireAnnuelSerializer
from authentication.permissions import IsAdminRole

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class InventaireAnnuelViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """XSTK13 — inventaire annuel légal FIGÉ (CGNC). LECTURE SEULE : un
    snapshot n'est créé QUE par l'action `figer`, jamais modifié ensuite.
    INTERNE (admin) — les coûts d'achat ne sont jamais client-facing."""
    queryset = InventaireAnnuel.objects.all()
    serializer_class = InventaireAnnuelSerializer
    permission_classes = [IsAdminRole]
    ordering = ['-exercice']

    @action(detail=False, methods=['post'], url_path='figer')
    def figer(self, request):
        """Fige l'inventaire de l'exercice donné (`{"exercice": 2026}`) —
        un exercice déjà figé pour cette société renvoie 400 (jamais
        ré-écrit)."""
        from ..services import figer_inventaire_annuel
        try:
            exercice = int(request.data.get('exercice'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Exercice invalide (attendu une année).'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            inventaire = figer_inventaire_annuel(
                request.user.company, exercice, request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(inventaire).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='export-xlsx')
    def export_xlsx(self, request, pk=None):
        """Export .xlsx du snapshot figé (relit `donnees`, jamais recalculé)."""
        from ..services import export_inventaire_annuel_xlsx
        inventaire = self.get_object()
        return export_inventaire_annuel_xlsx(inventaire)
