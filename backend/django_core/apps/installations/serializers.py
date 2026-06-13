from rest_framework import serializers

from .models import Installation, Intervention, InstallationActivity


class InstallationActivitySerializer(serializers.ModelSerializer):
    user_nom = serializers.SerializerMethodField()

    class Meta:
        model = InstallationActivity
        fields = [
            'id', 'kind', 'field', 'field_label', 'old_value', 'new_value',
            'body', 'user_nom', 'created_at',
        ]

    def get_user_nom(self, obj):
        return getattr(obj.user, 'username', None)


class InterventionSerializer(serializers.ModelSerializer):
    type_intervention_display = serializers.CharField(
        source='get_type_intervention_display', read_only=True)
    technicien_nom = serializers.SerializerMethodField()

    class Meta:
        model = Intervention
        fields = '__all__'
        # company/created_by posés côté serveur — jamais depuis le corps.
        read_only_fields = ['company', 'created_by', 'date_creation']

    def get_technicien_nom(self, obj):
        return getattr(obj.technicien, 'username', None)


class InstallationSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    raccordement_display = serializers.CharField(
        source='get_raccordement_display', read_only=True, default=None)
    type_installation_display = serializers.CharField(
        source='get_type_installation_display', read_only=True, default=None)
    # Position dans l'entonnoir — pour un tri non-alphabétique côté UI.
    statut_ordre = serializers.SerializerMethodField()
    client_nom = serializers.SerializerMethodField()
    technicien_nom = serializers.SerializerMethodField()
    devis_reference = serializers.CharField(
        source='devis.reference', read_only=True, default=None)
    lead_nom = serializers.SerializerMethodField()
    interventions = InterventionSerializer(many=True, read_only=True)
    nb_interventions = serializers.SerializerMethodField()

    class Meta:
        model = Installation
        fields = '__all__'
        # company/reference/created_by posés côté serveur — jamais du corps.
        read_only_fields = [
            'company', 'reference', 'created_by',
            'date_creation', 'date_modification',
        ]

    def get_statut_ordre(self, obj):
        order = list(Installation.STATUT_ORDER)
        try:
            return order.index(obj.statut)
        except ValueError:
            return len(order)

    def get_client_nom(self, obj):
        c = obj.client
        if not c:
            return None
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_technicien_nom(self, obj):
        return getattr(obj.technicien_responsable, 'username', None)

    def get_lead_nom(self, obj):
        if not obj.lead_id:
            return None
        return f"{obj.lead.nom} {obj.lead.prenom or ''}".strip()

    def get_nb_interventions(self, obj):
        return obj.interventions.count()
