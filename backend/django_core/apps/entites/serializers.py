from rest_framework import serializers

from .models import Entite


class EntiteSerializer(serializers.ModelSerializer):
    parent_nom = serializers.CharField(source='parent.nom', read_only=True)

    class Meta:
        model = Entite
        fields = [
            'id', 'nom', 'code', 'parent', 'parent_nom', 'actif',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_parent(self, value):
        if value is None:
            return value
        company = self.context['request'].user.company
        if value.company_id != company.id:
            raise serializers.ValidationError(
                "Le parent doit appartenir à la même société.")
        return value
