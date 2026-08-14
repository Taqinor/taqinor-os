from rest_framework import serializers

from .models import PosteDeCharge


class PosteDeChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PosteDeCharge
        fields = [
            'id', 'code', 'nom', 'type_poste', 'capacite_heures_jour',
            'cout_horaire', 'calendrier_travail', 'actif',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
