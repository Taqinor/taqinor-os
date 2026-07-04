from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import ContratMaintenance


class ContratMaintenanceSerializer(serializers.ModelSerializer):
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    prochaine_visite = serializers.SerializerMethodField()
    due = serializers.SerializerMethodField()
    renouvellement_du = serializers.SerializerMethodField()
    # FG40 — facturation récurrente.
    prochaine_facturation = serializers.SerializerMethodField()
    facturation_due = serializers.SerializerMethodField()
    # XCTR2 — registre des équipements couverts (lecture enrichie).
    equipements_detail = serializers.SerializerMethodField()

    class Meta:
        model = ContratMaintenance
        fields = ['id', 'client', 'client_nom', 'installation', 'periodicite',
                  'date_debut', 'derniere_visite', 'prix', 'actif', 'notes',
                  'duree_mois', 'date_renouvellement', 'renouvellement_du',
                  'prochaine_visite', 'due',
                  # FG40
                  'facturation_active', 'derniere_facturation',
                  'prochaine_facturation', 'facturation_due',
                  # XSAV7 — overrides SLA optionnels du contrat.
                  'sla_response_days', 'sla_resolution_days',
                  # XCTR2 — registre des équipements couverts.
                  'equipements', 'equipements_detail',
                  'date_creation']
        read_only_fields = ['derniere_visite', 'derniere_facturation', 'date_creation']

    def get_equipements_detail(self, obj):
        return [
            {
                'id': e.id,
                'numero_serie': getattr(e, 'numero_serie', None),
                'produit_nom': getattr(e.produit, 'nom', None),
            }
            for e in obj.equipements.select_related('produit').all()
        ]

    def validate_equipements(self, value):
        """XCTR2 — un équipement d'une autre société est refusé (400) : le
        registre de couverture ne doit jamais lier du matériel étranger."""
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return value
        for equipement in value:
            if equipement.company_id != company.id:
                raise ValidationError('Équipement inconnu.')
        return value

    def get_prochaine_visite(self, obj):
        return obj.prochaine_visite().isoformat()

    def get_due(self, obj):
        return obj.is_due()

    def get_renouvellement_du(self, obj):
        return obj.renouvellement_du()

    def get_prochaine_facturation(self, obj):
        """Date du prochain cycle de facturation (FG40)."""
        return obj.prochaine_facturation().isoformat()

    def get_facturation_due(self, obj):
        """True si la facturation récurrente est due (FG40)."""
        return obj.facturation_due()
