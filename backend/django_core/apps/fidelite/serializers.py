from rest_framework import serializers

from .models import (
    CompteFidelite, MouvementFidelite, PalierFidelite, ProgrammeFidelite,
)


class ProgrammeFideliteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgrammeFidelite
        fields = ['id', 'nom', 'actif', 'points_par_mad',
                  'valeur_mad_par_point', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class PalierFideliteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PalierFidelite
        fields = ['id', 'programme', 'libelle', 'ordre', 'seuil_points',
                  'seuil_ca_cumule', 'remise_pct', 'points_bonus_pct']
        read_only_fields = ['id']

    def validate(self, attrs):
        seuil_points = attrs.get(
            'seuil_points', getattr(self.instance, 'seuil_points', None))
        seuil_ca = attrs.get(
            'seuil_ca_cumule', getattr(self.instance, 'seuil_ca_cumule', None))
        if seuil_points is None and seuil_ca is None:
            raise serializers.ValidationError(
                "Un palier doit porter un seuil de points ou de CA cumulé.")
        return attrs

    def validate_programme(self, value):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        company_id = getattr(user, 'company_id', None)
        if company_id is not None and value.company_id != company_id:
            raise serializers.ValidationError(
                "Programme introuvable pour cette société.")
        return value


class MouvementFideliteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MouvementFidelite
        fields = ['id', 'type_mouvement', 'points', 'source_type',
                  'source_id', 'montant_source', 'motif', 'created_at']
        read_only_fields = fields


class CompteFideliteSerializer(serializers.ModelSerializer):
    palier_libelle = serializers.SerializerMethodField()

    class Meta:
        model = CompteFidelite
        fields = ['id', 'client', 'solde_points', 'palier_actuel',
                  'palier_libelle', 'created_at']
        read_only_fields = ['id', 'solde_points', 'palier_actuel',
                            'palier_libelle', 'created_at']

    def get_palier_libelle(self, obj):
        return obj.palier_actuel.libelle if obj.palier_actuel_id else None
