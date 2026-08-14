from rest_framework import serializers

from .models import CompteFidelite, MouvementFidelite, ProgrammeFidelite


class ProgrammeFideliteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgrammeFidelite
        fields = ['id', 'nom', 'actif', 'points_par_mad',
                  'valeur_mad_par_point', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class MouvementFideliteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MouvementFidelite
        fields = ['id', 'type_mouvement', 'points', 'source_type',
                  'source_id', 'montant_source', 'motif', 'created_at']
        read_only_fields = fields


class CompteFideliteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompteFidelite
        fields = ['id', 'client', 'solde_points', 'created_at']
        read_only_fields = ['id', 'solde_points', 'created_at']
