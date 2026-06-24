"""QJ16-wiring — ViewSet pour les presets de devis (modèles de devis).

Endpoints :
  GET    /ventes/presets/           list des presets de la société
  DELETE /ventes/presets/{id}/      supprime un preset de la société

Les actions save-preset et apply-preset vivent sur DevisViewSet
(POST /ventes/devis/{id}/save-preset/ et /apply-preset/).

Multi-tenancy : company toujours forcée côté serveur ; jamais lue du corps.
RULE #4 : ce viewset est CREATION-FREE côté preset — la création passe par
          save-preset sur le DevisViewSet qui garantit que la company vient
          du devis (pas de la requête).
"""
from rest_framework import viewsets, status
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from ..models import DevisPreset
from ..serializers import DevisPresetSerializer


class DevisPresetViewSet(viewsets.GenericViewSet):
    """QJ16 — Gestion des presets de devis (modèles de devis).

    Expose uniquement list + destroy : la création passe par
    ``POST /ventes/devis/{id}/save-preset/`` (company forcée depuis devis).
    """
    serializer_class = DevisPresetSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if not getattr(user, 'company_id', None):
            return DevisPreset.objects.none()
        return (
            DevisPreset.objects
            .filter(company=user.company)
            .select_related('created_by')
            .order_by('nom')
        )

    def list(self, request):
        """GET /presets/ — liste les presets de la société de l'utilisateur."""
        qs = self.get_queryset()
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def destroy(self, request, pk=None):
        """DELETE /presets/{id}/ — supprime un preset de la société."""
        qs = self.get_queryset()
        try:
            preset = qs.get(pk=pk)
        except DevisPreset.DoesNotExist:
            return Response(
                {'detail': 'Modèle introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        preset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
