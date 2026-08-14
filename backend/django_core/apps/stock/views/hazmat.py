"""NTWMS38 — référentiel des compatibilités casier ↔ matière dangereuse."""
from rest_framework import serializers

from authentication.permissions import (
    IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from core.viewsets import CompanyScopedModelViewSet

from ..models import CompatibiliteHazmatCasier, Produit

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class CompatibiliteHazmatCasierSerializer(serializers.ModelSerializer):
    bin_code = serializers.CharField(source='bin.code', read_only=True,
                                     default='')

    class Meta:
        model = CompatibiliteHazmatCasier
        fields = ['id', 'bin', 'bin_code', 'classe_danger', 'created_at']
        read_only_fields = ['created_at']

    def validate_classe_danger(self, value):
        valides = {c for c, _ in Produit.ClasseDanger.choices}
        if value not in valides:
            raise serializers.ValidationError(
                'Classe de danger inconnue.')
        if value == Produit.ClasseDanger.AUCUNE:
            raise serializers.ValidationError(
                "La classe « Aucune » n'a pas à être autorisée : un produit "
                'non dangereux est accepté partout.')
        return value


class CompatibiliteHazmatCasierViewSet(CompanyScopedModelViewSet):
    """CRUD des casiers autorisés par classe de danger.

    Lecture tout rôle (le magasinier doit savoir où ranger une batterie) ;
    écriture responsable/admin ; suppression admin.
    """
    queryset = CompatibiliteHazmatCasier.objects.select_related('bin').all()
    serializer_class = CompatibiliteHazmatCasierSerializer
    ordering = ['bin_id', 'classe_danger']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        # Filtrage MANUEL : aucun DjangoFilterBackend n'est branché ici, donc
        # `filterset_fields` serait un no-op silencieux.
        qs = super().get_queryset()
        bin_id = self.request.query_params.get('bin')
        if bin_id:
            qs = qs.filter(bin_id=bin_id)
        classe = self.request.query_params.get('classe_danger')
        if classe:
            qs = qs.filter(classe_danger=classe)
        return qs
