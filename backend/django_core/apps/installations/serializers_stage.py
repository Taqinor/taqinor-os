"""CH5 — Sérialiseur de configuration des étapes/gates de chantier (StageModele).

Édition réservée au Directeur (cf. la vue). Le sérialiseur expose l'ordre, le
drapeau bloquant, les exigences (`exige_*`) et le statut hérité mappé ; `cle`
et `protege` sont posés/verrouillés côté serveur pour les étapes système.
"""
from rest_framework import serializers

from .models import StageModele


class StageModeleSerializer(serializers.ModelSerializer):
    statut_legacy_display = serializers.CharField(
        source='get_statut_legacy_display', read_only=True, default=None)

    class Meta:
        model = StageModele
        fields = [
            'id', 'cle', 'libelle', 'ordre', 'bloquant',
            'exige_checklist', 'exige_photos', 'exige_series', 'exige_tests',
            'exige_materiel', 'exige_dossier', 'exige_pack',
            'statut_legacy', 'statut_legacy_display', 'actif', 'protege',
        ]
        # `protege` est un verrou système : jamais modifiable via l'API.
        read_only_fields = ['protege']

    def validate_cle(self, value):
        # La clé d'une étape SYSTÈME (protégée) est stable — on ne la renomme
        # pas (elle porte le mapping des effets de bord). Les étapes créées par
        # le Directeur gardent leur clé libre.
        if self.instance and self.instance.protege and value != self.instance.cle:
            raise serializers.ValidationError(
                "La clé d'une étape système ne peut pas être modifiée.")
        return value
