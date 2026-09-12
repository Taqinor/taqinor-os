"""ViewSets du module GRC & Conformité (NTGRC).

Tout viewset hérite de ``core.viewsets.CompanyScopedModelViewSet`` (ARC2) :
queryset filtré sur ``request.user.company`` et ``company`` imposée côté
serveur dans ``perform_create``/``perform_update``, jamais lue du corps.
"""
from authentication.permissions import IsAdminOrResponsableTier
from core.viewsets import CompanyScopedModelViewSet

from .models import PolitiqueRetentionObjet
from .serializers import PolitiqueRetentionObjetSerializer


class PolitiqueRetentionObjetViewSet(CompanyScopedModelViewSet):
    """NTGRC4 — CRUD des politiques de rétention par type d'objet.

    Donnée de CONFORMITÉ : réservée au palier admin/responsable, comme les
    registres RGPD de ``core`` (consentement, DSR, traitements CNDP). Pas de
    nouveau code de permission inventé — la même classe que ces registres.
    """

    queryset = PolitiqueRetentionObjet.objects.all()
    serializer_class = PolitiqueRetentionObjetSerializer
    permission_classes = [IsAdminOrResponsableTier]
