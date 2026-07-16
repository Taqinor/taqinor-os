from rest_framework import serializers

from .models import Departement


class DepartementSerializer(serializers.ModelSerializer):
    responsable_nom = serializers.SerializerMethodField()

    class Meta:
        model = Departement
        fields = [
            'id', 'company', 'code', 'nom', 'responsable', 'responsable_nom',
            'parent', 'actif', 'date_creation',
        ]
        read_only_fields = ['id', 'company', 'date_creation']

    def get_responsable_nom(self, obj):
        if obj.responsable_id:
            return (getattr(obj.responsable, 'get_full_name', lambda: '')()
                    or obj.responsable.username)
        return ''
