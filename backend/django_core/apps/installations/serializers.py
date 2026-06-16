from rest_framework import serializers

from .models import (
    ChecklistItem, Installation, Intervention, InstallationActivity,
    TypeIntervention,
)


class ChecklistItemSerializer(serializers.ModelSerializer):
    done_by_nom = serializers.SerializerMethodField()

    class Meta:
        model = ChecklistItem
        fields = [
            'id', 'label', 'ordre', 'done', 'done_by', 'done_by_nom', 'done_at',
        ]
        # done/done_by/done_at posés côté serveur via l'endpoint de bascule.
        read_only_fields = ['done', 'done_by', 'done_at']

    def get_done_by_nom(self, obj):
        return getattr(obj.done_by, 'username', None)


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


class TypeInterventionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeIntervention
        fields = ['id', 'key', 'label', 'ordre', 'archived']
        read_only_fields = ['key']

    def validate_label(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Libellé requis.')
        return value


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
    checklist = ChecklistItemSerializer(many=True, read_only=True)
    completion = serializers.SerializerMethodField()

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

    def get_completion(self, obj):
        """Avancement de la checklist : {done, total, percent} (0–100)."""
        items = obj.checklist.all()
        total = len(items)
        done = sum(1 for it in items if it.done)
        percent = round(done * 100 / total) if total else 0
        return {'done': done, 'total': total, 'percent': percent}


class ParcInstalleSerializer(serializers.ModelSerializer):
    """Vue « parc installé » d'un système installé (chantier réceptionné, N8).

    Lecture seule, orientée client-asset : JAMAIS de prix d'achat / marge. Porte
    les coordonnées GPS pour la carte et un résumé des marques des composants
    pour le filtre/affichage.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    type_installation_display = serializers.CharField(
        source='get_type_installation_display', read_only=True, default=None)
    client_nom = serializers.SerializerMethodField()
    technicien_nom = serializers.SerializerMethodField()
    devis_reference = serializers.CharField(
        source='devis.reference', read_only=True, default=None)
    marques = serializers.SerializerMethodField()
    nb_equipements = serializers.SerializerMethodField()

    class Meta:
        model = Installation
        fields = [
            'id', 'reference', 'statut', 'statut_display',
            'type_installation', 'type_installation_display',
            'client', 'client_nom', 'devis', 'devis_reference', 'lead',
            'site_adresse', 'site_ville', 'gps_lat', 'gps_lng',
            'puissance_installee_kwc', 'raccordement',
            'technicien_responsable', 'technicien_nom',
            'date_mise_en_service', 'date_reception', 'parc_actif',
            'marques', 'nb_equipements',
        ]

    def get_client_nom(self, obj):
        c = obj.client
        if not c:
            return None
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_technicien_nom(self, obj):
        return getattr(obj.technicien_responsable, 'username', None)

    def get_marques(self, obj):
        marques = []
        for eq in obj.equipements.all():
            m = getattr(eq.produit, 'marque', None)
            if m and m not in marques:
                marques.append(m)
        return marques

    def get_nb_equipements(self, obj):
        return obj.equipements.count()
