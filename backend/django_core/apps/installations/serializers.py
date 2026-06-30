from rest_framework import serializers

from .models import (
    Installation, Intervention, InstallationActivity, InterventionActivity,
    TypeIntervention, ChecklistTemplate, ChecklistEtapeModele,
    ChantierChecklistItem, ShotListSlot, InterventionPreparation,
    PreparationMaterielLigne, PreparationOutilLigne,
    ComponentSerial, PhotoAnnotation, MaterielConsommation, ConsommationLigne,
    VoiceMemo, Reserve, ToolReturn, SafetyChecklistSlot, SafetySignoff,
    SafetyCheckItem,
    TypeInterventionPlan,
    JalonProjet, ModeleProjet, ModeleProjetJalon, ModeleProjetBomLigne,
    ReunionChantier,
    DocumentProjet, RevisionDocument,
    Projet, ProjetTache, ProjetChantier, ProjetDevis, ProjetTicket,
    BudgetProjet, BudgetEngagement,
    IndisponibiliteRessource,
    SousTraitant,
    OrdreSousTraitance,
    FactureSousTraitant,
    PaiementSousTraitant,
    AttestationSousTraitant,
    EvaluationSousTraitant,
    RetenueGarantieSousTraitant,
    DemandeAchat,
    DemandeAchatLigne,
    RFQ,
    RFQOffre,
    SeuilApprobationBCF,
    ApprobationBCF,
)


class ChecklistEtapeModeleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistEtapeModele
        fields = ['id', 'template', 'cle', 'libelle', 'ordre', 'capture_serie',
                  # FG76 — gate photo obligatoire.
                  'photo_obligatoire',
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
                  # FG76 — photo obligatoire.
                  'photo_obligatoire',
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
    # F15 — temps d'équipe (durée sur site + trajet, minutes).
    crew_time = serializers.SerializerMethodField()
    # F16 — nombre de réserves ouvertes.
    reserves_ouvertes = serializers.SerializerMethodField()

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

    def get_crew_time(self, obj):
        from .field_capture import crew_time
        return crew_time(obj)

    def get_reserves_ouvertes(self, obj):
        return obj.reserves.filter(statut=Reserve.Statut.OUVERTE).count()


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
    # Parc — état de garantie AGRÉGÉ du système (le PIRE état parmi ses
    # équipements posés). Lecture seule : un repère pour la liste du parc, dérivé
    # du même calcul que sav.Equipement.garantie_etat. None si aucun équipement.
    parc_garantie_etat = serializers.SerializerMethodField()

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

    def get_parc_garantie_etat(self, obj):
        # Pire état de garantie parmi les équipements EN SERVICE du système.
        # Sévérité : hors_garantie > expire_bientot > non_renseignee >
        # sous_garantie. Mêmes seuils que sav (90 j « expire bientôt »). None
        # quand le système n'a encore aucun équipement enregistré.
        from datetime import date
        equipements = [
            eq for eq in obj.equipements.all()
            if eq.statut != 'remplace'
        ]
        if not equipements:
            return None
        today = date.today()
        severity = {
            'hors_garantie': 3, 'expire_bientot': 2,
            'non_renseignee': 1, 'sous_garantie': 0,
        }
        worst = 'sous_garantie'
        for eq in equipements:
            fin = eq.date_fin_garantie
            if not fin:
                etat = 'non_renseignee'
            else:
                jours = (fin - today).days
                if jours < 0:
                    etat = 'hors_garantie'
                elif jours <= 90:
                    etat = 'expire_bientot'
                else:
                    etat = 'sous_garantie'
            if severity[etat] > severity[worst]:
                worst = etat
        return worst

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


# ── F9 — n° de série de composant ────────────────────────────────────────────
class ComponentSerialSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    plaque_url = serializers.SerializerMethodField()

    class Meta:
        model = ComponentSerial
        fields = ['id', 'intervention', 'produit', 'produit_nom', 'designation',
                  'slot_cle', 'numero_serie', 'plaque_attachment', 'plaque_url',
                  'serie_ocr', 'pousse_parc', 'date_creation']
        read_only_fields = ['intervention', 'serie_ocr', 'pousse_parc',
                            'date_creation']

    def get_plaque_url(self, obj):
        if not obj.plaque_attachment_id:
            return None
        return (f'/api/django/records/attachments/'
                f'{obj.plaque_attachment_id}/download/')


# ── F10 — annotation de photo ────────────────────────────────────────────────
class PhotoAnnotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhotoAnnotation
        fields = ['id', 'attachment', 'drawing', 'caption', 'probleme',
                  'date_modification']
        read_only_fields = ['attachment', 'date_modification']


# ── F11/F12 — réconciliation matériel consommé ───────────────────────────────
class ConsommationLigneSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    variance = serializers.SerializerMethodField()
    justification_requise = serializers.SerializerMethodField()

    class Meta:
        model = ConsommationLigne
        fields = ['id', 'produit', 'produit_nom', 'designation',
                  'quantite_prevue', 'quantite_utilisee', 'hors_nomenclature',
                  'justification', 'justification_memo', 'stock_applique',
                  'variance', 'justification_requise', 'ordre']
        read_only_fields = ['stock_applique', 'ordre']

    def get_variance(self, obj):
        return obj.variance

    def get_justification_requise(self, obj):
        from .field_capture import ligne_needs_justification
        return ligne_needs_justification(obj)


class MaterielConsommationSerializer(serializers.ModelSerializer):
    lignes = ConsommationLigneSerializer(many=True, read_only=True)
    valide_par_nom = serializers.SerializerMethodField()
    nb_variances = serializers.SerializerMethodField()
    overage = serializers.SerializerMethodField()

    class Meta:
        model = MaterielConsommation
        fields = ['id', 'intervention', 'valide', 'valide_par_nom', 'valide_le',
                  'lignes', 'nb_variances', 'overage']
        read_only_fields = ['intervention', 'valide', 'valide_le']

    def get_valide_par_nom(self, obj):
        return getattr(obj.valide_par, 'username', None)

    def get_nb_variances(self, obj):
        return sum(1 for li in obj.lignes.all() if li.variance != 0)

    def get_overage(self, obj):
        from .field_capture import consommation_overage
        return consommation_overage(obj)


# ── F13/F14 — mémo vocal ──────────────────────────────────────────────────────
class VoiceMemoSerializer(serializers.ModelSerializer):
    audio_url = serializers.SerializerMethodField()
    created_by_nom = serializers.SerializerMethodField()

    class Meta:
        model = VoiceMemo
        fields = ['id', 'intervention', 'cible', 'audio', 'audio_url',
                  'transcript', 'transcrit', 'created_by_nom', 'date_creation']
        read_only_fields = ['intervention', 'audio', 'transcrit',
                            'date_creation']

    def get_audio_url(self, obj):
        if not obj.audio_id:
            return None
        return f'/api/django/records/attachments/{obj.audio_id}/download/'

    def get_created_by_nom(self, obj):
        return getattr(obj.created_by, 'username', None)


# ── F16 — réserve (punch-list) ────────────────────────────────────────────────
class ReserveSerializer(serializers.ModelSerializer):
    assignee_nom = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Reserve
        fields = ['id', 'intervention', 'description', 'photo', 'photo_url',
                  'memo', 'assignee', 'assignee_nom', 'statut', 'statut_display',
                  'resolution', 'resolue_le', 'suivi_intervention', 'ticket',
                  'date_creation']
        read_only_fields = ['intervention', 'suivi_intervention', 'ticket',
                            'resolue_le', 'date_creation']

    def get_assignee_nom(self, obj):
        return getattr(obj.assignee, 'username', None)

    def get_photo_url(self, obj):
        if not obj.photo_id:
            return None
        return f'/api/django/records/attachments/{obj.photo_id}/download/'


# ── F17 — retour d'outil ─────────────────────────────────────────────────────
class ToolReturnSerializer(serializers.ModelSerializer):
    outil_nom = serializers.CharField(
        source='outil.nom', read_only=True, default=None)
    emplacement_nom = serializers.CharField(
        source='emplacement_retour.nom', read_only=True, default=None)

    class Meta:
        model = ToolReturn
        fields = ['id', 'intervention', 'outil', 'outil_nom', 'rendu',
                  'emplacement_retour', 'emplacement_nom', 'note', 'confirme_le']
        read_only_fields = ['intervention', 'outil', 'confirme_le']


# ── F18 — consignes de sécurité ──────────────────────────────────────────────
class SafetyChecklistSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SafetyChecklistSlot
        fields = ['id', 'cle', 'libelle', 'ordre', 'actif', 'protege']
        read_only_fields = ['protege']

    def validate_cle(self, value):
        if self.instance and self.instance.protege and value != self.instance.cle:
            raise serializers.ValidationError(
                "La clé d'une consigne protégée ne peut pas être modifiée.")
        return value


class SafetyCheckItemSerializer(serializers.ModelSerializer):
    coche_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = SafetyCheckItem
        fields = ['id', 'cle', 'libelle', 'ordre', 'coche', 'coche_par_nom',
                  'coche_le']

    def get_coche_par_nom(self, obj):
        return getattr(obj.coche_par, 'username', None)


class SafetySignoffSerializer(serializers.ModelSerializer):
    items = SafetyCheckItemSerializer(many=True, read_only=True)
    signe_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = SafetySignoff
        fields = ['id', 'intervention', 'signe', 'signe_par_nom', 'signe_le',
                  'items']
        read_only_fields = ['intervention', 'signe', 'signe_le']

    def get_signe_par_nom(self, obj):
        return getattr(obj.signe_par, 'username', None)


# ── FG79 — Plan d'interventions standard ─────────────────────────────────────

class TypeInterventionPlanSerializer(serializers.ModelSerializer):
    """FG79 — sérialise un élément du plan d'interventions standard
    (type_installation + type_intervention_cle + ordre)."""
    type_installation_display = serializers.CharField(
        source='get_type_installation_display', read_only=True)

    class Meta:
        model = TypeInterventionPlan
        fields = [
            'id', 'type_installation', 'type_installation_display',
            'type_intervention_cle', 'libelle_contexte', 'ordre',
        ]
        # company posée côté serveur.
        read_only_fields = []


# ── FG293 — Jalons & phases de projet ────────────────────────────────────────

class JalonProjetSerializer(serializers.ModelSerializer):
    """FG293 — jalon/phase de projet d'un chantier (dates cible & réelle)."""
    phase_display = serializers.CharField(
        source='get_phase_display', read_only=True, default=None)

    class Meta:
        model = JalonProjet
        fields = [
            'id', 'installation', 'phase', 'phase_display', 'libelle', 'ordre',
            'date_cible', 'date_reelle', 'atteint', 'notes',
            'date_creation', 'date_modification',
        ]
        # company posée côté serveur ; jamais lue du corps.
        read_only_fields = ['date_creation', 'date_modification']


# ── FG296 — Modèles de projet (templates de chantier-type) ───────────────────

class ModeleProjetJalonSerializer(serializers.ModelSerializer):
    phase_display = serializers.CharField(
        source='get_phase_display', read_only=True, default=None)

    class Meta:
        model = ModeleProjetJalon
        fields = [
            'id', 'phase', 'phase_display', 'libelle', 'ordre', 'offset_jours',
        ]


class ModeleProjetBomLigneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeleProjetBomLigne
        fields = ['id', 'produit', 'designation', 'quantite', 'ordre']


class ModeleProjetSerializer(serializers.ModelSerializer):
    """FG296 — modèle de projet (chantier-type) + ses jalons/BoM type imbriqués
    en lecture. La société est posée côté serveur, jamais lue du corps."""
    jalons = ModeleProjetJalonSerializer(many=True, read_only=True)
    bom_lignes = ModeleProjetBomLigneSerializer(many=True, read_only=True)
    type_installation_display = serializers.CharField(
        source='get_type_installation_display', read_only=True, default=None)

    class Meta:
        model = ModeleProjet
        fields = [
            'id', 'nom', 'type_installation', 'type_installation_display',
            'description', 'actif', 'jalons', 'bom_lignes',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


# ── FG298 — Comptes-rendus de réunion de chantier ────────────────────────────

class ReunionChantierSerializer(serializers.ModelSerializer):
    """FG298 — compte-rendu de réunion de chantier. `redige_par` et company
    posés côté serveur (jamais lus du corps)."""
    redige_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = ReunionChantier
        fields = [
            'id', 'installation', 'titre', 'date_reunion', 'ordre_du_jour',
            'presents', 'decisions', 'actions', 'redige_par', 'redige_par_nom',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'redige_par', 'date_creation', 'date_modification',
        ]

    def get_redige_par_nom(self, obj):
        return getattr(obj.redige_par, 'username', None)


# ── FG297 — Contrôle documentaire de projet ──────────────────────────────────

class RevisionDocumentSerializer(serializers.ModelSerializer):
    """FG297 — révision d'un document de projet. `auteur` posé côté serveur."""
    auteur_nom = serializers.SerializerMethodField()
    fichier_url = serializers.SerializerMethodField()

    class Meta:
        model = RevisionDocument
        fields = [
            'id', 'document', 'indice', 'date_revision',
            'auteur', 'auteur_nom', 'fichier', 'fichier_url',
            'notes', 'date_creation',
        ]
        read_only_fields = ['auteur', 'date_creation']

    def get_auteur_nom(self, obj):
        return getattr(obj.auteur, 'username', None)

    def get_fichier_url(self, obj):
        if not obj.fichier_id:
            return None
        return f'/api/django/records/attachments/{obj.fichier_id}/download/'


class DocumentProjetSerializer(serializers.ModelSerializer):
    """FG297 — document de projet avec ses révisions imbriquées (lecture).
    La société est posée côté serveur, jamais lue du corps."""
    type_doc_display = serializers.CharField(
        source='get_type_doc_display', read_only=True)
    inst_revisions = RevisionDocumentSerializer(many=True, read_only=True)
    nb_revisions = serializers.SerializerMethodField()

    class Meta:
        model = DocumentProjet
        fields = [
            'id', 'installation', 'type_doc', 'type_doc_display',
            'titre', 'notes', 'inst_revisions', 'nb_revisions',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def get_nb_revisions(self, obj):
        return obj.inst_revisions.count()


# ── FG291 — Programme / Projet multi-chantiers ───────────────────────────────

class ProjetChantierSerializer(serializers.ModelSerializer):
    """FG291 — rattachement d'un chantier à un programme. La société est posée
    côté serveur ; le chantier est validé tenant côté vue."""
    installation_reference = serializers.CharField(
        source='installation.reference', read_only=True, default=None)
    installation_statut = serializers.CharField(
        source='installation.statut', read_only=True, default=None)

    class Meta:
        model = ProjetChantier
        fields = [
            'id', 'projet', 'installation', 'installation_reference',
            'installation_statut', 'libelle', 'ordre', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class ProjetDevisSerializer(serializers.ModelSerializer):
    """FG291 — rattachement d'un devis à un programme (string-FK, statut intact)."""
    devis_reference = serializers.CharField(
        source='devis.reference', read_only=True, default=None)
    devis_statut = serializers.CharField(
        source='devis.statut', read_only=True, default=None)

    class Meta:
        model = ProjetDevis
        fields = [
            'id', 'projet', 'devis', 'devis_reference', 'devis_statut',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class ProjetTicketSerializer(serializers.ModelSerializer):
    """FG291 — rattachement d'un ticket SAV à un programme (string-FK, statut
    intact)."""
    ticket_reference = serializers.CharField(
        source='ticket.reference', read_only=True, default=None)
    ticket_statut = serializers.CharField(
        source='ticket.statut', read_only=True, default=None)

    class Meta:
        model = ProjetTicket
        fields = [
            'id', 'projet', 'ticket', 'ticket_reference', 'ticket_statut',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class ProjetSerializer(serializers.ModelSerializer):
    """FG291 — programme/projet multi-chantiers regroupant chantiers + devis +
    tickets d'un même client/site. `reference`, company et `created_by` sont
    posés côté serveur (jamais lus du corps). Le statut est PROPRE au programme
    (jamais l'entonnoir commercial). Les rattachements sont imbriqués en
    lecture."""
    reference = serializers.CharField(read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    responsable_nom = serializers.SerializerMethodField()
    chantiers = ProjetChantierSerializer(many=True, read_only=True)
    devis = ProjetDevisSerializer(many=True, read_only=True)
    tickets = ProjetTicketSerializer(many=True, read_only=True)
    nb_chantiers = serializers.SerializerMethodField()

    class Meta:
        model = Projet
        fields = [
            'id', 'reference', 'nom', 'client', 'site_adresse', 'site_ville',
            'statut', 'statut_display', 'description', 'date_debut',
            'date_fin_cible', 'responsable', 'responsable_nom',
            'chantiers', 'devis', 'tickets', 'nb_chantiers',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'date_creation', 'date_modification',
        ]

    def get_responsable_nom(self, obj):
        return getattr(obj.responsable, 'username', None)

    def get_nb_chantiers(self, obj):
        return obj.chantiers.count()


# ── FG292 — Tâches & sous-tâches de projet avec dépendances ───────────────────

class ProjetTacheSerializer(serializers.ModelSerializer):
    """FG292 — tâche/sous-tâche de programme avec dépendances. La société est
    posée côté serveur ; `projet`, `parent`, `predecesseur` et `assigne` sont
    validés tenant côté vue. Le statut est PROPRE à la tâche (jamais
    l'entonnoir commercial). Les sous-tâches sont imbriquées en lecture."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    assigne_nom = serializers.SerializerMethodField()
    predecesseur_libelle = serializers.CharField(
        source='predecesseur.libelle', read_only=True, default=None)
    nb_sous_taches = serializers.SerializerMethodField()

    class Meta:
        model = ProjetTache
        fields = [
            'id', 'projet', 'parent', 'predecesseur', 'predecesseur_libelle',
            'libelle', 'description', 'assigne', 'assigne_nom', 'date_echeance',
            'statut', 'statut_display', 'ordre', 'nb_sous_taches',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def get_assigne_nom(self, obj):
        return getattr(obj.assigne, 'username', None)

    def get_nb_sous_taches(self, obj):
        return obj.sous_taches.count()


# ── FG294 — Budget projet vs réel (engagé / dépensé) ──────────────────────────

class BudgetEngagementSerializer(serializers.ModelSerializer):
    """FG294 — rattachement d'un coût fournisseur (BCF ou facture fournisseur)
    à un budget de programme, par string-FK (jamais d'import des modèles stock).
    `source`/`categorie` ventilent la dépense ; la société est posée côté
    serveur."""
    source_display = serializers.CharField(
        source='get_source_display', read_only=True, default=None)
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True, default=None)

    class Meta:
        model = BudgetEngagement
        fields = [
            'id', 'budget', 'source', 'source_display',
            'categorie', 'categorie_display',
            'bon_commande', 'facture', 'libelle', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate(self, attrs):
        """L'engagement doit pointer le bon objet selon `source` : un BCF pour
        `bon_commande`, une facture pour `facture` — jamais les deux ni aucun."""
        source = attrs.get(
            'source', getattr(self.instance, 'source', None))
        bon = attrs.get(
            'bon_commande', getattr(self.instance, 'bon_commande', None))
        facture = attrs.get(
            'facture', getattr(self.instance, 'facture', None))
        if source == BudgetEngagement.Source.BON_COMMANDE:
            if bon is None:
                raise serializers.ValidationError(
                    {'bon_commande': 'Requis pour un engagement « bon de '
                                     'commande ».'})
            if facture is not None:
                raise serializers.ValidationError(
                    {'facture': 'À laisser vide pour un bon de commande.'})
        elif source == BudgetEngagement.Source.FACTURE:
            if facture is None:
                raise serializers.ValidationError(
                    {'facture': 'Requis pour un engagement « facture ».'})
            if bon is not None:
                raise serializers.ValidationError(
                    {'bon_commande': 'À laisser vide pour une facture.'})
        return attrs


class BudgetProjetSerializer(serializers.ModelSerializer):
    """FG294 — budget d'un programme (enveloppes par catégorie + seuil d'alerte).
    La société et `created_by` sont posés côté serveur ; le `projet` est validé
    tenant côté vue. Ne touche aucun statut. La synthèse vs réel (engagé/dépensé,
    dépassement) est exposée par l'action `synthese` de la vue, calculée par le
    sélecteur `budget_projet_synthese`."""
    budget_total = serializers.SerializerMethodField()
    engagements = BudgetEngagementSerializer(many=True, read_only=True)

    class Meta:
        model = BudgetProjet
        fields = [
            'id', 'projet', 'devise',
            'budget_materiel', 'budget_main_oeuvre', 'budget_sous_traitance',
            'budget_divers', 'budget_total', 'tarif_jour_mo',
            'seuil_alerte_pct', 'note', 'engagements',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def get_budget_total(self, obj):
        return float(obj.budget_total)

    def validate_seuil_alerte_pct(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError(
                'Le seuil d\'alerte doit être compris entre 0 et 100 %.')
        return value


class IndisponibiliteRessourceSerializer(serializers.ModelSerializer):
    """FG302 — créneau d'indisponibilité d'une ressource terrain (technicien OU
    camionnette) sur [date_debut, date_fin]. La société et `created_by` sont
    posés côté serveur ; la garde « exactement une cible + ordre des dates » est
    validée ici (et re-validée côté modèle via `clean`)."""
    type_indispo_display = serializers.CharField(
        source='get_type_indispo_display', read_only=True, default=None)
    technicien_nom = serializers.SerializerMethodField()
    camionnette_nom = serializers.CharField(
        source='camionnette.nom', read_only=True, default=None)

    class Meta:
        model = IndisponibiliteRessource
        fields = [
            'id', 'technicien', 'technicien_nom',
            'camionnette', 'camionnette_nom',
            'type_indispo', 'type_indispo_display',
            'date_debut', 'date_fin', 'motif',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['created_by', 'date_creation', 'date_modification']

    def get_technicien_nom(self, obj):
        user = getattr(obj, 'technicien', None)
        if user is None:
            return None
        getter = getattr(user, 'get_full_name', None)
        nom = (getter() or '').strip() if callable(getter) else ''
        return nom or getattr(user, 'username', None)

    def validate(self, attrs):
        """Exactement UNE cible (technicien XOR camionnette) et `date_fin` ≥
        `date_debut`. Sur une mise à jour partielle, on retombe sur la valeur
        déjà persistée pour le champ non fourni."""
        def _resolved(field):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, None)

        technicien = _resolved('technicien')
        camionnette = _resolved('camionnette')
        if technicien is None and camionnette is None:
            raise serializers.ValidationError(
                {'technicien': 'Indiquez une ressource (technicien ou '
                               'camionnette).'})
        if technicien is not None and camionnette is not None:
            raise serializers.ValidationError(
                {'camionnette': 'Une indisponibilité vise UNE seule ressource '
                                '(technicien OU camionnette, pas les deux).'})

        debut = _resolved('date_debut')
        fin = _resolved('date_fin')
        if debut is not None and fin is not None and fin < debut:
            raise serializers.ValidationError(
                {'date_fin': 'La date de fin doit être postérieure ou égale à '
                             'la date de début.'})
        return attrs


class SousTraitantSerializer(serializers.ModelSerializer):
    """FG304 — annuaire des sous-traitants chantier (main-d'œuvre sous-traitée),
    DISTINCT des fournisseurs de matériel. La société et `created_by` sont posés
    côté serveur (jamais lus du corps). `metier_display` expose le libellé
    français du code de métier."""
    metier_display = serializers.CharField(
        source='get_metier_display', read_only=True, default=None)
    # Un sous-traitant est ACTIF par défaut. Déclaré explicitement pour rester
    # indépendant du type de contenu : en form-data, un BooleanField DRF absent
    # est lu comme False (sémantique case à cocher), ce qui écraserait le
    # défaut du modèle. `default=True` garantit « actif » à la création quel que
    # soit le client ; l'archivage reste possible en envoyant `actif=false`.
    actif = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = SousTraitant
        fields = [
            'id', 'raison_sociale', 'metier', 'metier_display',
            'contact_nom', 'telephone', 'email', 'ice', 'rib', 'adresse',
            'actif', 'note',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['created_by', 'date_creation', 'date_modification']

    def validate_raison_sociale(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError(
                'La raison sociale est obligatoire.')
        return value


class OrdreSousTraitanceSerializer(serializers.ModelSerializer):
    """FG305 — ordre de travaux émis à un sous-traitant (FG304). La référence,
    la société et `created_by` sont posés CÔTÉ SERVEUR (jamais lus du corps) ;
    `reference` est anti-collision (`OST-YYYYMM-NNNN`). `statut_display` et
    `sous_traitant_nom` exposent des libellés lisibles. Le `statut` n'est pas
    piloté par l'API d'écriture standard — il avance via les actions de cycle de
    vie (`emettre`/`receptionner`/`cloturer`)."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    sous_traitant_nom = serializers.CharField(
        source='sous_traitant.raison_sociale', read_only=True, default=None)

    class Meta:
        model = OrdreSousTraitance
        fields = [
            'id', 'reference', 'sous_traitant', 'sous_traitant_nom',
            'chantier', 'prestation', 'montant', 'montant_realise',
            'date_emission', 'date_echeance', 'statut', 'statut_display',
            'note', 'created_by', 'date_creation', 'date_modification',
        ]
        # La référence, le créateur et les horodatages sont posés serveur. Le
        # statut n'est jamais écrit librement : il avance via les actions de
        # cycle de vie (lecture seule ici).
        read_only_fields = [
            'reference', 'statut', 'created_by',
            'date_creation', 'date_modification',
        ]

    def validate_prestation(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError(
                'La prestation est obligatoire.')
        return value

    def validate_montant(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le montant ne peut pas être négatif.')
        return value

    def validate_montant_realise(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le montant réalisé ne peut pas être négatif.')
        return value


class PaiementSousTraitantSerializer(serializers.ModelSerializer):
    """FG306 — règlement imputé sur une facture sous-traitant. La société et
    `created_by` sont posés CÔTÉ SERVEUR (jamais lus du corps). Le montant est
    INTERNE — jamais client-facing."""
    mode_display = serializers.CharField(
        source='get_mode_display', read_only=True, default=None)

    class Meta:
        model = PaiementSousTraitant
        fields = [
            'id', 'facture', 'montant', 'date_paiement',
            'mode', 'mode_display', 'reference_paiement', 'note',
            'created_by', 'date_creation',
        ]
        read_only_fields = ['created_by', 'date_creation']

    def validate_montant(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError(
                'Le montant du paiement doit être strictement positif.')
        return value


class FactureSousTraitantSerializer(serializers.ModelSerializer):
    """FG306 — facture entrante d'un sous-traitant chantier (compte à payer
    main-d'œuvre). La société et `created_by` sont posés CÔTÉ SERVEUR. Le `statut`
    n'est pas écrit librement : il avance via les actions de cycle de vie
    (`a_payer`/`payer`/`annuler`) et le reflet automatique des paiements. Tous les
    montants sont INTERNES — jamais client-facing."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    sous_traitant_nom = serializers.CharField(
        source='sous_traitant.raison_sociale', read_only=True, default=None)
    total_paye = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    reste_a_payer = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    paiements = PaiementSousTraitantSerializer(many=True, read_only=True)

    class Meta:
        model = FactureSousTraitant
        fields = [
            'id', 'numero', 'sous_traitant', 'sous_traitant_nom',
            'ordre', 'chantier',
            'montant_ht', 'montant_tva', 'montant_ttc',
            'date_facture', 'date_echeance',
            'statut', 'statut_display', 'note',
            'total_paye', 'reste_a_payer', 'paiements',
            'created_by', 'date_creation', 'date_modification',
        ]
        # Le statut avance via les actions de cycle de vie / le reflet des
        # paiements — jamais écrit librement.
        read_only_fields = [
            'statut', 'created_by', 'date_creation', 'date_modification',
        ]

    def validate_montant_ttc(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le montant TTC ne peut pas être négatif.')
        return value


class AttestationSousTraitantSerializer(serializers.ModelSerializer):
    """FG307 — pièce administrative obligatoire d'un sous-traitant (CNSS, RC
    décennale, agrément…). La société et `created_by` sont posés CÔTÉ SERVEUR.
    `est_valide` expose si la pièce est encore valide aujourd'hui (lecture
    seule)."""
    type_piece_display = serializers.CharField(
        source='get_type_piece_display', read_only=True, default=None)
    sous_traitant_nom = serializers.CharField(
        source='sous_traitant.raison_sociale', read_only=True, default=None)
    est_valide = serializers.SerializerMethodField()
    obligatoire = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = AttestationSousTraitant
        fields = [
            'id', 'sous_traitant', 'sous_traitant_nom',
            'type_piece', 'type_piece_display', 'reference', 'organisme',
            'date_emission', 'date_expiration', 'obligatoire', 'note',
            'est_valide',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['created_by', 'date_creation', 'date_modification']

    def get_est_valide(self, obj):
        return obj.est_valide()


class EvaluationSousTraitantSerializer(serializers.ModelSerializer):
    """FG308 — note de performance d'un sous-traitant (qualité/délai/sécurité,
    1–5). La société et `evalue_par` sont posés CÔTÉ SERVEUR. `note_globale` est
    la moyenne dérivée des trois axes (lecture seule)."""
    sous_traitant_nom = serializers.CharField(
        source='sous_traitant.raison_sociale', read_only=True, default=None)
    note_globale = serializers.DecimalField(
        max_digits=3, decimal_places=1, read_only=True)

    class Meta:
        model = EvaluationSousTraitant
        fields = [
            'id', 'sous_traitant', 'sous_traitant_nom', 'ordre', 'chantier',
            'note_qualite', 'note_delai', 'note_securite', 'note_globale',
            'commentaire', 'date_evaluation',
            'evalue_par', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['evalue_par', 'date_creation', 'date_modification']

    def _validate_note(self, value, champ):
        if value is None or value < 1 or value > 5:
            raise serializers.ValidationError(
                f'La note {champ} doit être comprise entre 1 et 5.')
        return value

    def validate_note_qualite(self, value):
        return self._validate_note(value, 'qualité')

    def validate_note_delai(self, value):
        return self._validate_note(value, 'délai')

    def validate_note_securite(self, value):
        return self._validate_note(value, 'sécurité')


class RetenueGarantieSousTraitantSerializer(serializers.ModelSerializer):
    """FG309 — retenue de garantie (%) sur un ordre de sous-traitance, bloquée
    jusqu'à la levée des réserves. La société et `created_by` sont posés CÔTÉ
    SERVEUR. `levee`/`date_levee` n'avancent que par l'action `lever` —
    `montant_retenu`/`montant_a_liberer` sont dérivés (lecture seule). Montants
    INTERNES."""
    ordre_reference = serializers.CharField(
        source='ordre.reference', read_only=True, default=None)
    montant_base = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    montant_retenu = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    montant_a_liberer = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = RetenueGarantieSousTraitant
        fields = [
            'id', 'ordre', 'ordre_reference', 'pourcentage',
            'levee', 'date_constitution', 'date_levee', 'note',
            'montant_base', 'montant_retenu', 'montant_a_liberer',
            'created_by', 'date_creation', 'date_modification',
        ]
        # La levée n'est jamais écrite librement : elle avance via l'action
        # `lever`.
        read_only_fields = [
            'levee', 'date_levee', 'created_by',
            'date_creation', 'date_modification',
        ]

    def validate_pourcentage(self, value):
        if value is None or value < 0 or value > 100:
            raise serializers.ValidationError(
                'Le pourcentage doit être compris entre 0 et 100.')
        return value


class DemandeAchatLigneSerializer(serializers.ModelSerializer):
    """FG310 — ligne d'une demande d'achat (produit catalogue OU désignation
    libre, quantité, prix estimé INTERNE)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    total_estime = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = DemandeAchatLigne
        fields = [
            'id', 'demande', 'produit', 'produit_nom', 'designation',
            'quantite', 'prix_estime', 'total_estime',
        ]

    def validate(self, attrs):
        produit = attrs.get('produit') if 'produit' in attrs else getattr(
            self.instance, 'produit', None)
        designation = attrs.get('designation') if 'designation' in attrs else (
            getattr(self.instance, 'designation', None))
        if produit is None and not (designation or '').strip():
            raise serializers.ValidationError(
                {'designation': 'Indiquez un produit ou une désignation.'})
        return attrs


class DemandeAchatSerializer(serializers.ModelSerializer):
    """FG310 — réquisition d'achat soumise à approbation. La référence, la
    société et `created_by` sont posés CÔTÉ SERVEUR ; `reference` est
    anti-collision (`DA-YYYYMM-NNNN`). Le `statut`, l'approbateur et la date de
    décision avancent via les actions de cycle de vie
    (`soumettre`/`approuver`/`refuser`/`marquer_commandee`) — jamais écrits
    librement. `montant_estime` est dérivé (INTERNE)."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    priorite_display = serializers.CharField(
        source='get_priorite_display', read_only=True, default=None)
    lignes = DemandeAchatLigneSerializer(many=True, read_only=True)
    montant_estime = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = DemandeAchat
        fields = [
            'id', 'reference', 'objet', 'chantier', 'programme',
            'fournisseur_suggere', 'priorite', 'priorite_display',
            'date_besoin', 'statut', 'statut_display', 'motif_refus',
            'approuvee_par', 'date_decision', 'note', 'lignes',
            'montant_estime',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'approuvee_par', 'date_decision',
            'motif_refus', 'created_by', 'date_creation', 'date_modification',
        ]

    def validate_objet(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError("L'objet est obligatoire.")
        return value


class RFQOffreSerializer(serializers.ModelSerializer):
    """FG311 — réponse d'un fournisseur à une RFQ (montant HT, délai, validité).
    La société est posée CÔTÉ SERVEUR ; `retenue` n'avance que par l'action
    `retenir` de la RFQ (lecture seule ici). Montants INTERNES."""
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True, default=None)

    class Meta:
        model = RFQOffre
        fields = [
            'id', 'rfq', 'fournisseur', 'fournisseur_nom',
            'fournisseur_nom_libre', 'montant_ht', 'delai_jours',
            'validite_jours', 'retenue', 'note',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['retenue', 'date_creation', 'date_modification']

    def validate(self, attrs):
        fournisseur = attrs.get('fournisseur') if 'fournisseur' in attrs else (
            getattr(self.instance, 'fournisseur', None))
        libre = attrs.get('fournisseur_nom_libre') if (
            'fournisseur_nom_libre' in attrs) else getattr(
            self.instance, 'fournisseur_nom_libre', None)
        if fournisseur is None and not (libre or '').strip():
            raise serializers.ValidationError(
                {'fournisseur': 'Indiquez un fournisseur ou un nom libre.'})
        return attrs

    def validate_montant_ht(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le montant HT ne peut pas être négatif.')
        return value


class RFQSerializer(serializers.ModelSerializer):
    """FG311 — demande de prix multi-fournisseurs. La référence et la société
    sont posées CÔTÉ SERVEUR ; `reference` est anti-collision
    (`RFQ-YYYYMM-NNNN`). Le `statut` avance via `envoyer`/`cloturer`. Les offres
    sont imbriquées en lecture ; `comparatif` résume moins-chère / plus-rapide /
    retenue."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    offres = RFQOffreSerializer(many=True, read_only=True)
    comparatif = serializers.SerializerMethodField()

    class Meta:
        model = RFQ
        fields = [
            'id', 'reference', 'objet', 'demande', 'date_limite_reponse',
            'statut', 'statut_display', 'note', 'offres', 'comparatif',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'created_by',
            'date_creation', 'date_modification',
        ]

    def get_comparatif(self, obj):
        from . import selectors
        return selectors.rfq_comparatif(obj)

    def validate_objet(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError("L'objet est obligatoire.")
        return value


class SeuilApprobationBCFSerializer(serializers.ModelSerializer):
    """FG312 — seuil (MAD) par société : un BCF au-dessus du seuil exige un
    Administrateur. La société est posée CÔTÉ SERVEUR."""

    class Meta:
        model = SeuilApprobationBCF
        fields = [
            'id', 'seuil_responsable', 'actif',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def validate_seuil_responsable(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le seuil ne peut pas être négatif.')
        return value


class ApprobationBCFSerializer(serializers.ModelSerializer):
    """FG312 — approbation d'un BCF (string-FK vers stock). Le palier, le montant
    approuvé, l'approbateur et la société sont posés CÔTÉ SERVEUR par l'action
    `approuver` ; ce serializer est essentiellement en lecture."""
    palier_display = serializers.CharField(
        source='get_palier_display', read_only=True, default=None)

    class Meta:
        model = ApprobationBCF
        fields = [
            'id', 'bcf', 'palier', 'palier_display', 'montant_approuve',
            'approuve_par', 'note', 'date_approbation',
        ]
        read_only_fields = [
            'palier', 'montant_approuve', 'approuve_par', 'date_approbation',
        ]
