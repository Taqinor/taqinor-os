from rest_framework import serializers

from .models import (
    Installation, Intervention, InstallationActivity, InterventionActivity,
    TypeIntervention, ChecklistTemplate, ChecklistEtapeModele,
    ChantierChecklistItem, ShotListSlot, InterventionPreparation,
    PreparationMaterielLigne, PreparationOutilLigne,
)


class ChecklistEtapeModeleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistEtapeModele
        fields = ['id', 'template', 'cle', 'libelle', 'ordre', 'capture_serie',
                  'actif', 'protege']
        read_only_fields = ['protege']

    def validate_cle(self, value):
        if self.instance and self.instance.protege and value != self.instance.cle:
            raise serializers.ValidationError(
                "La clé d'une étape protégée ne peut pas être modifiée.")
        return value


class ChecklistTemplateSerializer(serializers.ModelSerializer):
    """N74 — modèle nommé de checklist + ses étapes ordonnées (imbriquées en
    lecture). `type_installation` auto-sélectionne le template à la création
    d'un chantier ; le template « Défaut » (type vide) est le repli protégé."""
    etapes = ChecklistEtapeModeleSerializer(many=True, read_only=True)
    type_installation_display = serializers.CharField(
        source='get_type_installation_display', read_only=True, default=None)

    class Meta:
        model = ChecklistTemplate
        fields = ['id', 'nom', 'type_installation', 'type_installation_display',
                  'ordre', 'actif', 'protege', 'etapes']
        read_only_fields = ['protege']

    def validate_type_installation(self, value):
        # Le template « Défaut » (protégé, type vide) garde son type vide.
        if (self.instance and self.instance.protege
                and value != self.instance.type_installation):
            raise serializers.ValidationError(
                "Le type du template « Défaut » ne peut pas être modifié.")
        return value or None


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
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    # F3 — position du statut dans la machine à états PROPRE de l'intervention
    # (pour un tri kanban non-alphabétique). Aucun lien avec le chantier.
    statut_ordre = serializers.SerializerMethodField()
    technicien_nom = serializers.SerializerMethodField()
    equipe_noms = serializers.SerializerMethodField()
    camionnette_nom = serializers.CharField(
        source='camionnette.nom', read_only=True, default=None)
    # Données héritées du chantier (lecture seule) : référence, client, devis,
    # ville et GPS du site sont tirés de l'installation, jamais ressaisis.
    installation_reference = serializers.CharField(
        source='installation.reference', read_only=True, default=None)
    client_nom = serializers.SerializerMethodField()
    devis_reference = serializers.CharField(
        source='installation.devis.reference', read_only=True, default=None)
    site_ville = serializers.CharField(
        source='installation.site_ville', read_only=True, default=None)
    gps_lat = serializers.DecimalField(
        source='installation.gps_lat', max_digits=9, decimal_places=6,
        read_only=True, default=None)
    gps_lng = serializers.DecimalField(
        source='installation.gps_lng', max_digits=9, decimal_places=6,
        read_only=True, default=None)
    # F6 — distance (km) entre la position d'arrivée et le GPS du chantier.
    distance_site_km = serializers.SerializerMethodField()
    # F5 — avancement de la préparation (0–100, ou null si pas de préparation).
    preparation_completion = serializers.SerializerMethodField()
    preparation_confirmee = serializers.SerializerMethodField()
    # F8 — nombre de créneaux obligatoires sans photo (garde « Terminée »).
    photos_obligatoires_manquantes = serializers.SerializerMethodField()

    class Meta:
        model = Intervention
        fields = '__all__'
        # company/created_by posés côté serveur — jamais depuis le corps. Les
        # horodatages F6 et les coordonnées d'arrivée sont posés par leurs
        # endpoints dédiés (check-in/départ/retour), pas par un PATCH générique.
        read_only_fields = [
            'company', 'created_by', 'date_creation',
            'depart_depot_le', 'arrivee_site_le', 'retour_depot_le',
            'arrivee_gps_lat', 'arrivee_gps_lng',
        ]

    def get_statut_ordre(self, obj):
        order = list(Intervention.STATUT_ORDER)
        try:
            return order.index(obj.statut)
        except ValueError:
            return len(order)

    def get_technicien_nom(self, obj):
        return getattr(obj.technicien, 'username', None)

    def get_equipe_noms(self, obj):
        return [u.username for u in obj.equipe.all()]

    def get_client_nom(self, obj):
        c = getattr(obj.installation, 'client', None)
        if not c:
            return None
        return f"{c.nom} {c.prenom or ''}".strip()

    def get_distance_site_km(self, obj):
        from .field_services import distance_to_site
        return distance_to_site(obj)

    def get_preparation_completion(self, obj):
        from .field_services import preparation_completion
        prep = getattr(obj, 'preparation', None)
        if prep is None:
            return None
        return preparation_completion(prep)

    def get_preparation_confirmee(self, obj):
        prep = getattr(obj, 'preparation', None)
        return bool(prep and prep.tout_charge)

    def get_photos_obligatoires_manquantes(self, obj):
        from .field_services import missing_required_shots
        return len(missing_required_shots(obj))


class ShotListSlotSerializer(serializers.ModelSerializer):
    phase_display = serializers.CharField(
        source='get_phase_display', read_only=True)

    class Meta:
        model = ShotListSlot
        fields = ['id', 'cle', 'libelle', 'phase', 'phase_display',
                  'obligatoire', 'ordre', 'actif', 'protege']
        read_only_fields = ['protege']

    def validate_cle(self, value):
        if self.instance and self.instance.protege and value != self.instance.cle:
            raise serializers.ValidationError(
                "La clé d'un créneau protégé ne peut pas être modifiée.")
        return value

    def validate_phase(self, value):
        if value not in dict(ShotListSlot.Phase.choices):
            raise serializers.ValidationError("Phase inconnue.")
        return value


class PreparationMaterielLigneSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreparationMaterielLigne
        fields = ['id', 'produit', 'designation', 'quantite_requise',
                  'charge', 'manquant', 'quantite_manquante', 'ordre']
        read_only_fields = ['produit', 'designation', 'quantite_requise',
                            'manquant', 'quantite_manquante', 'ordre']


class PreparationOutilLigneSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreparationOutilLigne
        fields = ['id', 'outil', 'libelle', 'coche', 'ordre']
        read_only_fields = ['outil', 'libelle', 'ordre']


class InterventionPreparationSerializer(serializers.ModelSerializer):
    materiel = PreparationMaterielLigneSerializer(many=True, read_only=True)
    outils = PreparationOutilLigneSerializer(many=True, read_only=True)
    completion = serializers.SerializerMethodField()
    confirme_par_nom = serializers.SerializerMethodField()
    kit_nom = serializers.CharField(
        source='kit.nom', read_only=True, default=None)
    nb_manques = serializers.SerializerMethodField()

    class Meta:
        model = InterventionPreparation
        fields = ['id', 'intervention', 'kit', 'kit_nom', 'tout_charge',
                  'confirme_par_nom', 'confirme_le', 'materiel', 'outils',
                  'completion', 'nb_manques']
        read_only_fields = ['intervention', 'tout_charge', 'confirme_le']

    def get_completion(self, obj):
        from .field_services import preparation_completion
        return preparation_completion(obj)

    def get_confirme_par_nom(self, obj):
        return getattr(obj.confirme_par, 'username', None)

    def get_nb_manques(self, obj):
        return sum(1 for li in obj.materiel.all() if li.manquant)


class InterventionActivitySerializer(serializers.ModelSerializer):
    user_nom = serializers.SerializerMethodField()

    class Meta:
        model = InterventionActivity
        fields = [
            'id', 'kind', 'field', 'field_label', 'old_value', 'new_value',
            'body', 'user_nom', 'created_at',
        ]

    def get_user_nom(self, obj):
        return getattr(obj.user, 'username', None)


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
