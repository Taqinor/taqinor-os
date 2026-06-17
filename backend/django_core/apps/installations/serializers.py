from rest_framework import serializers

from .models import (
    Installation, Intervention, InstallationActivity, TypeIntervention,
    ChecklistEtapeModele, ChantierChecklistItem, ProductionReleve,
)


class ProductionReleveSerializer(serializers.ModelSerializer):
    """N51 — relevé de production (saisie manuelle / monitoring)."""
    source_label = serializers.CharField(
        source='get_source_display', read_only=True)
    nb_jours = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductionReleve
        fields = [
            'id', 'periode_debut', 'periode_fin', 'kwh_produit', 'source',
            'source_label', 'note', 'nb_jours', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate(self, attrs):
        debut = attrs.get('periode_debut')
        fin = attrs.get('periode_fin')
        if debut and fin and fin < debut:
            raise serializers.ValidationError(
                {'periode_fin': 'La fin doit être après le début.'})
        return attrs


class ChecklistEtapeModeleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistEtapeModele
        fields = ['id', 'cle', 'libelle', 'ordre', 'capture_serie',
                  'actif', 'protege']
        read_only_fields = ['protege']

    def validate_cle(self, value):
        if self.instance and self.instance.protege and value != self.instance.cle:
            raise serializers.ValidationError(
                "La clé d'une étape protégée ne peut pas être modifiée.")
        return value


class ChantierChecklistItemSerializer(serializers.ModelSerializer):
    fait_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = ChantierChecklistItem
        fields = ['id', 'cle', 'libelle', 'ordre', 'capture_serie',
                  'fait', 'fait_par_nom', 'fait_le']

    def get_fait_par_nom(self, obj):
        return getattr(obj.fait_par, 'username', None)


class TypeInterventionSerializer(serializers.ModelSerializer):
    en_usage = serializers.SerializerMethodField()

    class Meta:
        model = TypeIntervention
        fields = ['id', 'cle', 'libelle', 'ordre', 'protege', 'archived', 'en_usage']
        read_only_fields = ['protege']

    def get_en_usage(self, obj):
        return Intervention.objects.filter(
            company=obj.company, type_intervention=obj.cle).count()

    def validate_cle(self, value):
        if self.instance and self.instance.protege and value != self.instance.cle:
            raise serializers.ValidationError(
                "La clé d'un type protégé ne peut pas être modifiée.")
        return value


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
    # Statut rabattu sur sa colonne canonique (kanban/parc) — les valeurs
    # héritées tombent dans la bonne colonne sans réécrire la donnée stockée.
    statut_canonique = serializers.SerializerMethodField()
    # N7 — le chantier est-il un « système installé » actif (réceptionné) ?
    est_parc = serializers.SerializerMethodField()
    # N4 — avancement de la checklist d'exécution (0–100, ou null si vide).
    checklist_completion = serializers.SerializerMethodField()
    client_nom = serializers.SerializerMethodField()
    technicien_nom = serializers.SerializerMethodField()
    devis_reference = serializers.CharField(
        source='devis.reference', read_only=True, default=None)
    lead_nom = serializers.SerializerMethodField()
    interventions = InterventionSerializer(many=True, read_only=True)
    nb_interventions = serializers.SerializerMethodField()
    # N43 — régime loi 82-21 suggéré pour la puissance du chantier (seuils
    # éditables). Lecture seule : un repère, le champ regime_8221 reste maître.
    regime_suggere = serializers.SerializerMethodField()

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
            return order.index(Installation.canonical_statut(obj.statut))
        except ValueError:
            return len(order)

    def get_statut_canonique(self, obj):
        return Installation.canonical_statut(obj.statut)

    def get_regime_suggere(self, obj):
        from .regime import suggest_for_company
        code = suggest_for_company(obj.puissance_installee_kwc, obj.company)
        label = dict(Installation.Regime8221.choices).get(code, code)
        return {'code': code, 'label': label}

    def get_est_parc(self, obj):
        # Système installé = chantier réceptionné (ou clôturé) et toujours
        # actif dans le parc, hors chantier annulé.
        canon = Installation.canonical_statut(obj.statut)
        reached = canon in (
            Installation.Statut.RECEPTIONNE, Installation.Statut.CLOTURE)
        return bool(reached and obj.parc_actif and not obj.annule)

    def get_checklist_completion(self, obj):
        items = list(obj.checklist.all())
        if not items:
            return None
        done = sum(1 for it in items if it.fait)
        return round(100 * done / len(items))

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
