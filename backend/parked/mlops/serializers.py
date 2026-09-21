from rest_framework import serializers

from .models import ModeleML


class ModeleMLSerializer(serializers.ModelSerializer):
    nom_label = serializers.CharField(source='get_nom_display', read_only=True)

    class Meta:
        model = ModeleML
        # company posée côté serveur — jamais lue du corps.
        fields = [
            'id', 'nom', 'nom_label', 'version', 'params_json', 'actif',
            'note', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'nom_label', 'actif', 'created_at', 'updated_at']
