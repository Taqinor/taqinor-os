"""ViewSets du module GRC & Conformité (NTGRC).

Tout viewset hérite de ``core.viewsets.CompanyScopedModelViewSet`` (ARC2) :
queryset filtré sur ``request.user.company`` et ``company`` imposée côté
serveur dans ``perform_create``/``perform_update``, jamais lue du corps.
"""
from authentication.permissions import IsAdminOrResponsableTier
from core.viewsets import CompanyScopedModelViewSet

from .models import JournalDestruction, PolitiqueRetentionObjet
from .serializers import (
    JournalDestructionSerializer, PolitiqueRetentionObjetSerializer,
)


class PolitiqueRetentionObjetViewSet(CompanyScopedModelViewSet):
    """NTGRC4 — CRUD des politiques de rétention par type d'objet.

    Donnée de CONFORMITÉ : réservée au palier admin/responsable, comme les
    registres RGPD de ``core`` (consentement, DSR, traitements CNDP). Pas de
    nouveau code de permission inventé — la même classe que ces registres.
    """

    queryset = PolitiqueRetentionObjet.objects.all()
    serializer_class = PolitiqueRetentionObjetSerializer
    permission_classes = [IsAdminOrResponsableTier]


class JournalDestructionViewSet(CompanyScopedModelViewSet):
    """NTGRC5 — journal APPEND-ONLY des destructions/anonymisations.

    ``http_method_names`` n'expose QUE la lecture et la création : aucune
    route d'update ni de delete n'existe. La garde d'immuabilité vit aussi au
    niveau du modèle, pour qu'aucun autre chemin de code ne puisse réécrire
    une ligne.

    Filtres : ``?type_objet=`` et ``?depuis=`` / ``?jusqu_a=`` (dates ISO).
    """

    queryset = JournalDestruction.objects.all()
    serializer_class = JournalDestructionSerializer
    permission_classes = [IsAdminOrResponsableTier]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        type_objet = (params.get('type_objet') or '').strip()
        if type_objet:
            qs = qs.filter(type_objet=type_objet)
        depuis = (params.get('depuis') or '').strip()
        if depuis:
            qs = qs.filter(created_at__date__gte=depuis)
        jusqu_a = (params.get('jusqu_a') or '').strip()
        if jusqu_a:
            qs = qs.filter(created_at__date__lte=jusqu_a)
        return qs

    def perform_create(self, serializer):
        """``company`` ET l'acteur sont posés CÔTÉ SERVEUR, jamais lus du corps."""
        serializer.save(
            company=self.request.user.company,
            executee_par=getattr(self.request.user, 'username', '') or '')
