from rest_framework import serializers
from .models import ContratMaintenance


class ContratMaintenanceSerializer(serializers.ModelSerializer):
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    prochaine_visite = serializers.SerializerMethodField()
    due = serializers.SerializerMethodField()

    class Meta:
        model = ContratMaintenance
        fields = ['id', 'client', 'client_nom', 'installation', 'periodicite',
                  'date_debut', 'derniere_visite', 'prix', 'actif', 'notes',
                  'prochaine_visite', 'due', 'date_creation']
        read_only_fields = ['derniere_visite', 'date_creation']

    def get_prochaine_visite(self, obj):
        return obj.prochaine_visite().isoformat()

    def get_due(self, obj):
        return obj.is_due()
