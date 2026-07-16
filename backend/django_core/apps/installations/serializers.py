from rest_framework import serializers

from .models import (
    Equipe,
    Installation, Intervention, InstallationActivity, InterventionActivity,
    TypeIntervention, ChecklistTemplate, ChecklistEtapeModele,
    ChantierChecklistItem, ShotListSlot, InterventionPreparation,
    PreparationMaterielLigne, PreparationOutilLigne,
    ComponentSerial, PhotoAnnotation, MaterielConsommation, ConsommationLigne,
    VoiceMemo, Reserve, ToolReturn, SafetyChecklistSlot, SafetySignoff,
    ReverificationMesure,
    SafetyCheckItem,
    FicheInterventionTemplate, FicheInterventionChamp,
    FicheInterventionReleve, FicheInterventionValeur,
    RecurrenceIntervention,
    TypeInterventionPlan,
    JalonProjet, ModeleProjet, ModeleProjetJalon, ModeleProjetBomLigne,
    ReunionChantier,
    DocumentProjet, RevisionDocument,
    Projet, ProjetTache, ProjetChantier, ProjetDevis, ProjetTicket,
    BudgetProjet, BudgetEngagement,
    IndisponibiliteRessource,
    Astreinte,
    OrdreSousTraitance,
    AttestationSousTraitant,
    EvaluationSousTraitant,
    RetenueGarantieSousTraitant,
    DemandeAchat,
    DemandeAchatLigne,
    RFQ,
    RFQOffre,
    RFQConsultation,
    SeuilApprobationBCF,
    ApprobationBCF,
    CommandeCadre,
    CommandeCadreLigne,
    AppelCommande,
    DossierImport,
    FraisImport,
    LandedCostLigne,
    ReceptionNonFacturee,
    ContratPrixFournisseur,
    ContratPrixLigne,
    BinLocation,
    BinAffectation,
    PutAway,
    PickList,
    PickListLigne,
    Colis,
    ColisLigne,
    SerieEntrepot,
    SessionComptage,
    ComptageLigne,
    DemandeTransfert,
    RegleReappro,
    MaterielConsigne,
    Kit,
    KitComposant,
    RevisionKit,
    OrdreAssemblage,
    OrdreAssemblageActivity,
    OrdreAssemblageLigne,
    SerieAssemblage,
    OrdreDemontage,
    OrdreDemontageLigne,
    ControleQualiteModele,
    ControleQualiteItemModele,
    ControleQualiteOrdre,
    EtapeAssemblage,
    EtapeOrdre,
    Livraison,
    LivraisonLigne,
    PreuveLivraison,
    Transporteur,
    RetourMateriel,
    RetourMaterielLigne,
    RetourLivraison,
    RetourLivraisonLigne,
    CategorieStockage,
    RegleRangement,
    LotPrelevement,
    GpsConsentRecord,
    PositionTechnicien,
    GeofenceAlert,
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


class FicheInterventionChampSerializer(serializers.ModelSerializer):
    class Meta:
        model = FicheInterventionChamp
        fields = ['id', 'template', 'cle', 'libelle', 'type_champ', 'unite',
                  'ordre', 'obligatoire']


class FicheInterventionTemplateSerializer(serializers.ModelSerializer):
    """ZFSM1 — gabarit de fiche d'intervention + ses champs ordonnés (imbriqués
    en lecture). `type_intervention` sélectionne le gabarit appliqué à une
    intervention de ce type."""
    champs = FicheInterventionChampSerializer(many=True, read_only=True)

    class Meta:
        model = FicheInterventionTemplate
        fields = ['id', 'nom', 'type_intervention', 'actif', 'protege', 'champs']
        read_only_fields = ['protege']

    def validate_type_intervention(self, value):
        if (self.instance and self.instance.protege
                and value != self.instance.type_intervention):
            raise serializers.ValidationError(
                "Le type d'un gabarit protégé ne peut pas être modifié.")
        return value


class FicheInterventionValeurSerializer(serializers.ModelSerializer):
    champ_libelle = serializers.CharField(source='champ.libelle', read_only=True)
    champ_type = serializers.CharField(source='champ.type_champ', read_only=True)
    champ_unite = serializers.CharField(source='champ.unite', read_only=True)
    champ_obligatoire = serializers.BooleanField(
        source='champ.obligatoire', read_only=True)
    champ_cle = serializers.CharField(source='champ.cle', read_only=True)

    class Meta:
        model = FicheInterventionValeur
        fields = ['id', 'champ', 'champ_cle', 'champ_libelle', 'champ_type',
                  'champ_unite', 'champ_obligatoire', 'valeur', 'renseigne_le']
        read_only_fields = ['champ']


class FicheInterventionReleveSerializer(serializers.ModelSerializer):
    valeurs = FicheInterventionValeurSerializer(many=True, read_only=True)
    template_nom = serializers.CharField(
        source='template.nom', read_only=True, default=None)

    class Meta:
        model = FicheInterventionReleve
        fields = ['id', 'intervention', 'template', 'template_nom', 'valeurs',
                  'date_creation', 'date_modification']
        read_only_fields = ['intervention', 'template']


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
    # XFSM8 — notes d'accès du chantier, reprises en lecture sur chaque
    # intervention (jamais ressaisies) : affichées sur « Ma journée » F22 et
    # le compte-rendu F19.
    contact_site_nom = serializers.CharField(
        source='installation.contact_site_nom', read_only=True, default=None)
    contact_site_telephone = serializers.CharField(
        source='installation.contact_site_telephone', read_only=True, default=None)
    acces_instructions = serializers.CharField(
        source='installation.acces_instructions', read_only=True, default=None)
    horaires_acces = serializers.CharField(
        source='installation.horaires_acces', read_only=True, default=None)
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
            # XFSM21 — posé uniquement par le sweep Beat météo, jamais du corps.
            'meteo_risque', 'meteo_verifie_le',
            # YSERV6 — posés uniquement par le chemin d'annulation chantier
            # (annuler/reactiver), jamais par un PATCH générique.
            'annulee', 'motif_annulation',
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
                  'devis_repare_id', 'date_creation']
        read_only_fields = ['intervention', 'suivi_intervention', 'ticket',
                            'devis_repare_id', 'resolue_le', 'date_creation']

    def get_assignee_nom(self, obj):
        return getattr(obj.assignee, 'username', None)

    def get_photo_url(self, obj):
        if not obj.photo_id:
            return None
        return f'/api/django/records/attachments/{obj.photo_id}/download/'


# ── XFSM13 — re-vérification IEC 62446-2 vs baseline ────────────────────────
class ReverificationMesureSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReverificationMesure
        fields = [
            'id', 'intervention_id', 'record_baseline',
            'isolement_mohm', 'continuite_terre_ohm', 'voc_comparaison',
            'isolement_ecart_pct', 'seuil_alerte_pct', 'depassement_detecte',
            'reserve_id', 'observations', 'date_creation',
        ]
        read_only_fields = [
            'intervention_id', 'record_baseline', 'voc_comparaison',
            'isolement_ecart_pct', 'depassement_detecte', 'reserve_id',
            'date_creation',
        ]


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


# ── ZFSM3 — Interventions récurrentes autonomes ──────────────────────────────

class RecurrenceInterventionSerializer(serializers.ModelSerializer):
    """ZFSM3 — récurrence temporelle d'intervention (sans contrat). La
    société/l'installation sont scopées côté serveur ; `nb_generees` et
    `actif` sont dérivés par le générateur (lecture seule)."""
    regle_display = serializers.CharField(
        source='get_regle_display', read_only=True)
    installation_reference = serializers.CharField(
        source='installation.reference', read_only=True, default=None)
    technicien_defaut_nom = serializers.CharField(
        source='technicien_defaut.username', read_only=True, default=None)

    class Meta:
        model = RecurrenceIntervention
        fields = [
            'id', 'installation', 'installation_reference', 'type_intervention',
            'technicien_defaut', 'technicien_defaut_nom', 'regle', 'regle_display',
            'intervalle', 'prochaine_echeance', 'date_fin', 'nb_occurrences',
            'nb_generees', 'actif', 'date_creation',
        ]
        read_only_fields = ['nb_generees']


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
            'tranche_echeancier', 'rappel_facturation_envoye',
            'date_creation', 'date_modification',
        ]
        # company posée côté serveur ; jamais lue du corps.
        read_only_fields = [
            'date_creation', 'date_modification', 'rappel_facturation_envoye',
        ]


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


class EquipeSerializer(serializers.ModelSerializer):
    """DC40 — équipe terrain CANONIQUE. La société et `created_by` sont posés
    côté serveur (jamais lus du corps) ; les `membres` (M2M → utilisateurs) et
    le `chef` doivent appartenir à la société de l'utilisateur (validé côté
    viewset). Expose les noms des membres en lecture pour l'affichage."""
    membres_noms = serializers.SerializerMethodField()
    chef_nom = serializers.SerializerMethodField()
    nb_membres = serializers.SerializerMethodField()

    class Meta:
        model = Equipe
        fields = [
            'id', 'nom', 'membres', 'membres_noms', 'nb_membres',
            'chef', 'chef_nom', 'actif', 'description',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'company', 'created_by', 'date_creation', 'date_modification']

    @staticmethod
    def _nom(user):
        if user is None:
            return None
        getter = getattr(user, 'get_full_name', None)
        nom = (getter() or '').strip() if callable(getter) else ''
        return nom or getattr(user, 'username', None)

    def get_membres_noms(self, obj):
        return [self._nom(u) for u in obj.membres.all()]

    def get_chef_nom(self, obj):
        return self._nom(getattr(obj, 'chef', None))

    def get_nb_membres(self, obj):
        return obj.membres.count()


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


class AstreinteSerializer(serializers.ModelSerializer):
    """XFSM10 — période d'astreinte d'un technicien. Société + `created_by`
    posés côté serveur ; le chevauchement de périodes est validé au niveau
    modèle (`clean()`, remonté en 400 par la vue)."""
    technicien_nom = serializers.SerializerMethodField()

    class Meta:
        model = Astreinte
        fields = [
            'id', 'technicien', 'technicien_nom', 'date_debut', 'date_fin',
            'telephone_astreinte', 'created_by', 'date_creation',
        ]
        read_only_fields = ['created_by', 'date_creation']

    def get_technicien_nom(self, obj):
        user = getattr(obj, 'technicien', None)
        if user is None:
            return None
        getter = getattr(user, 'get_full_name', None)
        nom = (getter() or '').strip() if callable(getter) else ''
        return nom or getattr(user, 'username', None)

    def validate(self, attrs):
        def _resolved(field):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, None)

        debut = _resolved('date_debut')
        fin = _resolved('date_fin')
        if debut is not None and fin is not None and fin <= debut:
            raise serializers.ValidationError(
                {'date_fin': "La date de fin doit être après la date de début."})
        return attrs


class SousTraitantSerializer(serializers.Serializer):
    """DC34 — façade de l'annuaire des sous-traitants. Un sous-traitant N'EST
    PLUS un modèle parallèle : c'est un ``stock.Fournisseur`` de type « service »
    porteur d'un ``SousTraitantProfile``. Ce sérialiseur EXPOSE une vue à plat
    (raison sociale + métier + identité + archivage) au-dessus du couple
    Fournisseur/profil, et l'écriture passe par les services stock (société posée
    serveur). Aucun import de ``apps.stock.models`` — la vue orchestre via les
    sélecteurs/services stock.

    Le champ historique ``raison_sociale`` reste le libellé public (mappé sur
    ``Fournisseur.nom``) et ``contact_nom`` sur ``Fournisseur.contact_personne``
    pour préserver le contrat d'API FG304."""
    id = serializers.IntegerField(read_only=True)
    raison_sociale = serializers.CharField()
    metier = serializers.ChoiceField(
        choices=[  # miroir de stock.SousTraitantProfile.Metier
            ('terrassement', 'Terrassement'),
            ('genie_civil', 'Génie civil'),
            ('electricite', 'Électricité'),
            ('levage', 'Levage'),
            ('transport', 'Transport'),
            ('autre', 'Autre'),
        ],
        required=False, default='autre')
    metier_display = serializers.SerializerMethodField()
    contact_nom = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    telephone = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(
        required=False, allow_blank=True, allow_null=True)
    ice = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    rib = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    adresse = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    # Un sous-traitant est ACTIF par défaut ; `default=True` garantit « actif » à
    # la création quel que soit le type de contenu (un BooleanField absent en
    # form-data serait sinon lu comme False et écraserait le défaut).
    actif = serializers.BooleanField(required=False, default=True)
    note = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)
    date_creation = serializers.DateTimeField(read_only=True)
    date_modification = serializers.DateTimeField(read_only=True)

    _METIER_LABELS = {
        'terrassement': 'Terrassement', 'genie_civil': 'Génie civil',
        'electricite': 'Électricité', 'levage': 'Levage',
        'transport': 'Transport', 'autre': 'Autre',
    }

    def get_metier_display(self, obj):
        profil = getattr(obj, 'profil_sous_traitant', None)
        code = getattr(profil, 'metier', None)
        return self._METIER_LABELS.get(code)

    def validate_raison_sociale(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError(
                'La raison sociale est obligatoire.')
        return value

    def to_representation(self, obj):
        """`obj` est un stock.Fournisseur(type='service') ; on aplatit le couple
        Fournisseur + profil vers le contrat d'API FG304."""
        profil = getattr(obj, 'profil_sous_traitant', None)
        return {
            'id': obj.id,
            'raison_sociale': obj.nom,
            'metier': getattr(profil, 'metier', 'autre'),
            'metier_display': self.get_metier_display(obj),
            'contact_nom': obj.contact_personne,
            'telephone': obj.telephone,
            'email': obj.email,
            'ice': obj.ice,
            'rib': obj.rib,
            'adresse': obj.adresse,
            'actif': getattr(profil, 'actif', True),
            'note': getattr(profil, 'note', None),
            'date_creation': getattr(profil, 'date_creation', None),
            'date_modification': getattr(profil, 'date_modification', None),
        }


class OrdreSousTraitanceSerializer(serializers.ModelSerializer):
    """FG305 — ordre de travaux émis à un sous-traitant (FG304). La référence,
    la société et `created_by` sont posés CÔTÉ SERVEUR (jamais lus du corps) ;
    `reference` est anti-collision (`OST-YYYYMM-NNNN`). `statut_display` et
    `sous_traitant_nom` exposent des libellés lisibles. Le `statut` n'est pas
    piloté par l'API d'écriture standard — il avance via les actions de cycle de
    vie (`emettre`/`receptionner`/`cloturer`)."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    # DC34 — le sous-traitant est un stock.Fournisseur : son libellé est `nom`.
    sous_traitant_nom = serializers.CharField(
        source='sous_traitant.nom', read_only=True, default=None)

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


# DC34 — les sérialiseurs FactureSousTraitant/PaiementSousTraitant sont
# supprimés : l'AP sous-traitant passe par la chaîne standard stock
# (FactureFournisseur/PaiementFournisseur), et les vues façade `factures-sous-
# traitant`/`paiements-sous-traitant` sérialisent ces objets stock directement.


class AttestationSousTraitantSerializer(serializers.ModelSerializer):
    """FG307 — pièce administrative obligatoire d'un sous-traitant (CNSS, RC
    décennale, agrément…). La société et `created_by` sont posés CÔTÉ SERVEUR.
    `est_valide` expose si la pièce est encore valide aujourd'hui (lecture
    seule)."""
    type_piece_display = serializers.CharField(
        source='get_type_piece_display', read_only=True, default=None)
    sous_traitant_nom = serializers.CharField(
        source='sous_traitant.nom', read_only=True, default=None)  # DC34 Fournisseur.nom
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
        source='sous_traitant.nom', read_only=True, default=None)  # DC34 Fournisseur.nom
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
            'fournisseur_suggere', 'bon_commande', 'priorite',
            'priorite_display',
            'date_besoin', 'statut', 'statut_display', 'motif_refus',
            'approuvee_par', 'date_decision', 'note', 'lignes',
            'montant_estime',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'bon_commande', 'approuvee_par',
            'date_decision', 'motif_refus', 'created_by', 'date_creation',
            'date_modification',
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


class RFQConsultationSerializer(serializers.ModelSerializer):
    """XPUR20/21 — fournisseur consulté sur une RFQ : traçabilité d'envoi
    email/WhatsApp par destinataire + statut de réponse. Le `token` n'est
    JAMAIS exposé ici (le lien public se construit côté vue `envoyer`) — seul
    un flag `a_repondu` renseigne l'appelant."""
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True, default=None)
    fournisseur_email = serializers.CharField(
        source='fournisseur.email', read_only=True, default=None)
    fournisseur_telephone = serializers.CharField(
        source='fournisseur.telephone', read_only=True, default=None)
    a_repondu = serializers.BooleanField(read_only=True)

    class Meta:
        model = RFQConsultation
        fields = [
            'id', 'rfq', 'fournisseur', 'fournisseur_nom',
            'fournisseur_email', 'fournisseur_telephone',
            'email_envoye_le', 'whatsapp_envoye_le', 'derniere_relance_le',
            'nb_relances', 'a_repondu', 'offre',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'email_envoye_le', 'whatsapp_envoye_le', 'derniere_relance_le',
            'nb_relances', 'offre', 'date_creation', 'date_modification',
        ]


class RFQSerializer(serializers.ModelSerializer):
    """FG311 — demande de prix multi-fournisseurs. La référence et la société
    sont posées CÔTÉ SERVEUR ; `reference` est anti-collision
    (`RFQ-YYYYMM-NNNN`). Le `statut` avance via `envoyer`/`cloturer`. Les offres
    sont imbriquées en lecture ; `comparatif` résume moins-chère / plus-rapide /
    retenue. XPUR20 — `consultations` liste les fournisseurs invités + leur
    statut d'envoi/réponse."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    offres = RFQOffreSerializer(many=True, read_only=True)
    consultations = RFQConsultationSerializer(many=True, read_only=True)
    comparatif = serializers.SerializerMethodField()

    class Meta:
        model = RFQ
        fields = [
            'id', 'reference', 'objet', 'demande', 'date_limite_reponse',
            'statut', 'statut_display', 'bon_commande', 'note', 'offres',
            'consultations', 'comparatif',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'bon_commande', 'created_by',
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


class CommandeCadreLigneSerializer(serializers.ModelSerializer):
    """FG314 — ligne d'un contrat-cadre (SKU, prix négocié INTERNE, volume
    engagé). `volume_consomme`/`volume_restant` sont dérivés (lecture seule)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    volume_consomme = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)
    volume_restant = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CommandeCadreLigne
        fields = [
            'id', 'commande_cadre', 'produit', 'produit_nom', 'designation',
            'prix_negocie', 'volume_engage',
            'volume_consomme', 'volume_restant',
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


class CommandeCadreSerializer(serializers.ModelSerializer):
    """FG314 — contrat-cadre (prix négociés + volume engagé). La référence et la
    société sont posées CÔTÉ SERVEUR ; `reference` est anti-collision
    (`CC-YYYYMM-NNNN`). Le `statut` avance via `activer`/`cloturer`. Les lignes
    sont imbriquées en lecture."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True, default=None)
    lignes = CommandeCadreLigneSerializer(many=True, read_only=True)

    class Meta:
        model = CommandeCadre
        fields = [
            'id', 'reference', 'intitule', 'fournisseur', 'fournisseur_nom',
            'date_debut', 'date_fin', 'statut', 'statut_display', 'note',
            'lignes', 'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'created_by',
            'date_creation', 'date_modification',
        ]

    def validate_intitule(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError("L'intitulé est obligatoire.")
        return value


class AppelCommandeSerializer(serializers.ModelSerializer):
    """FG314 — commande d'appel sur une ligne de contrat-cadre. La société et
    `created_by` sont posés CÔTÉ SERVEUR. `montant` est dérivé (quantité × prix
    négocié, INTERNE)."""
    montant = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = AppelCommande
        fields = [
            'id', 'ligne', 'quantite', 'date_appel', 'chantier', 'note',
            'montant', 'created_by', 'date_creation',
        ]
        read_only_fields = ['created_by', 'date_creation']

    def validate_quantite(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError(
                'La quantité appelée doit être strictement positive.')
        return value


class DossierImportSerializer(serializers.ModelSerializer):
    """FG315 — dossier d'import / dédouanement d'un conteneur. La référence et la
    société sont posées CÔTÉ SERVEUR ; `reference` est anti-collision
    (`IMP-YYYYMM-NNNN`). Le `statut_douane` avance via l'action `avancer`."""
    statut_douane_display = serializers.CharField(
        source='get_statut_douane_display', read_only=True, default=None)
    incoterm_display = serializers.CharField(
        source='get_incoterm_display', read_only=True, default=None)
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True, default=None)

    class Meta:
        model = DossierImport
        fields = [
            'id', 'reference', 'designation', 'fournisseur', 'fournisseur_nom',
            'bon_commande', 'incoterm', 'incoterm_display', 'numero_bl',
            'numero_conteneur', 'port_arrivee', 'date_depart',
            'date_arrivee_port', 'date_dedouanement',
            'statut_douane', 'statut_douane_display', 'note',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut_douane', 'created_by',
            'date_creation', 'date_modification',
        ]

    def validate_designation(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError("La désignation est obligatoire.")
        return value


class FraisImportSerializer(serializers.ModelSerializer):
    """FG316 — frais imputé à un dossier d'import (fret/douane/TVA import/
    transit…). La société et `created_by` sont posés CÔTÉ SERVEUR. Montant
    INTERNE."""
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True, default=None)

    class Meta:
        model = FraisImport
        fields = [
            'id', 'dossier', 'categorie', 'categorie_display', 'libelle',
            'montant', 'date_frais', 'created_by', 'date_creation',
        ]
        read_only_fields = ['created_by', 'date_creation']

    def validate_montant(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le montant ne peut pas être négatif.')
        return value


class LandedCostLigneSerializer(serializers.ModelSerializer):
    """FG316 — ligne de coût débarqué par SKU (valeur FOB + quantité). La société
    est posée CÔTÉ SERVEUR. `cout_fob_unitaire` est dérivé ; la quote-part de
    frais + le coût débarqué se lisent via l'action `landed-cost` du dossier."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    cout_fob_unitaire = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = LandedCostLigne
        fields = [
            'id', 'dossier', 'produit', 'produit_nom', 'designation',
            'quantite', 'valeur_fob', 'cout_fob_unitaire', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate(self, attrs):
        produit = attrs.get('produit') if 'produit' in attrs else getattr(
            self.instance, 'produit', None)
        designation = attrs.get('designation') if 'designation' in attrs else (
            getattr(self.instance, 'designation', None))
        if produit is None and not (designation or '').strip():
            raise serializers.ValidationError(
                {'designation': 'Indiquez un produit ou une désignation.'})
        return attrs


class ReceptionNonFactureeSerializer(serializers.ModelSerializer):
    """FG317 — provision de dette latente (réceptionné-non-facturé). La société
    et `created_by` sont posés CÔTÉ SERVEUR ; `lettre`/`date_lettrage`/`facture`
    n'avancent que par l'action `lettrer`. `montant_a_provisionner` est dérivé
    (0 une fois lettré). Montants INTERNES."""
    montant_a_provisionner = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = ReceptionNonFacturee
        fields = [
            'id', 'reception', 'bon_commande', 'facture', 'libelle',
            'montant_provision', 'date_reception',
            'lettre', 'date_lettrage', 'note', 'montant_a_provisionner',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'facture', 'lettre', 'date_lettrage', 'created_by',
            'date_creation', 'date_modification',
        ]

    def validate_montant_provision(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError(
                'Le montant provisionné ne peut pas être négatif.')
        return value


class ContratPrixLigneSerializer(serializers.ModelSerializer):
    """FG318 — ligne de prix convenu d'un contrat fournisseur (SKU + prix
    négocié INTERNE + remise % optionnelle)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)

    class Meta:
        model = ContratPrixLigne
        fields = [
            'id', 'contrat', 'produit', 'produit_nom', 'designation',
            'prix_convenu', 'remise_pct',
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


class ContratPrixFournisseurSerializer(serializers.ModelSerializer):
    """FG318 — contrat de prix fournisseur daté/versionné. La référence et la
    société sont posées CÔTÉ SERVEUR ; `reference` est anti-collision
    (`CPF-YYYYMM-NNNN`). Le `statut` avance via `activer`/`expirer`. Les lignes
    sont imbriquées en lecture."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True, default=None)
    lignes = ContratPrixLigneSerializer(many=True, read_only=True)

    class Meta:
        model = ContratPrixFournisseur
        fields = [
            'id', 'reference', 'intitule', 'fournisseur', 'fournisseur_nom',
            'version', 'date_debut', 'date_fin', 'statut', 'statut_display',
            'note', 'lignes', 'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'created_by',
            'date_creation', 'date_modification',
        ]

    def validate_intitule(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError("L'intitulé est obligatoire.")
        return value


class BinAffectationSerializer(serializers.ModelSerializer):
    """FG319 — affectation produit ↔ casier (quantité indicative)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)

    class Meta:
        model = BinAffectation
        fields = [
            'id', 'bin', 'produit', 'produit_nom', 'quantite',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']


class BinLocationSerializer(serializers.ModelSerializer):
    """FG319 — casier de rangement adressable sous un `EmplacementStock`. La
    societe et `created_by` sont poses COTE SERVEUR. Les affectations produit
    sont imbriquees en lecture."""
    emplacement_nom = serializers.CharField(
        source='emplacement.nom', read_only=True, default=None)
    categorie_nom = serializers.CharField(
        source='categorie.nom', read_only=True, default=None)
    affectations = BinAffectationSerializer(many=True, read_only=True)

    class Meta:
        model = BinLocation
        fields = [
            'id', 'emplacement', 'emplacement_nom', 'code', 'zone', 'allee',
            'casier', 'ordre', 'categorie', 'categorie_nom', 'note',
            'archived', 'affectations',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'created_by', 'date_creation', 'date_modification',
        ]

    def validate_code(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le code du casier est requis.')
        return value


class PutAwaySerializer(serializers.ModelSerializer):
    """FG320 - rangement guide. La societe, `created_by`, `bin_suggere`, le
    statut et les champs de tracage sont poses COTE SERVEUR. Le magasinier
    confirme via l'action `ranger` (qui pose `bin_effectif`/`range_par`/date)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    bin_suggere_code = serializers.CharField(
        source='bin_suggere.code', read_only=True, default=None)
    bin_effectif_code = serializers.CharField(
        source='bin_effectif.code', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)

    class Meta:
        model = PutAway
        fields = [
            'id', 'produit', 'produit_nom', 'emplacement', 'quantite',
            'bin_suggere', 'bin_suggere_code',
            'bin_effectif', 'bin_effectif_code',
            'statut', 'statut_display', 'reference_reception', 'note',
            'range_par', 'date_rangement',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'bin_suggere', 'bin_effectif', 'statut', 'range_par',
            'date_rangement', 'created_by',
            'date_creation', 'date_modification',
        ]


class PickListLigneSerializer(serializers.ModelSerializer):
    """FG321 - ligne de prelevement (SKU + casier + avancement)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    bin_code = serializers.CharField(
        source='bin.code', read_only=True, default=None)

    class Meta:
        model = PickListLigne
        fields = [
            'id', 'pick_list', 'produit', 'produit_nom', 'designation',
            'bin', 'bin_code', 'quantite_demandee', 'quantite_prelevee',
            'ordre', 'preleve',
        ]
        read_only_fields = ['pick_list', 'ordre']


class PickListSerializer(serializers.ModelSerializer):
    """FG321 - bon de prelevement d'un chantier. La reference, la societe et
    `created_by` sont poses COTE SERVEUR ; les lignes sont generees serveur
    depuis les reservations (action `generer`) et imbriquees en lecture."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    lignes = PickListLigneSerializer(many=True, read_only=True)

    class Meta:
        model = PickList
        fields = [
            'id', 'reference', 'installation', 'statut', 'statut_display',
            'note', 'lignes', 'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'created_by',
            'date_creation', 'date_modification',
        ]


class ColisLigneSerializer(serializers.ModelSerializer):
    """FG322 - article emballe dans un colis (SKU + quantite + controle OK)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)

    class Meta:
        model = ColisLigne
        fields = [
            'id', 'colis', 'produit', 'produit_nom', 'designation',
            'quantite', 'controle_ok',
        ]

    def validate(self, attrs):
        produit = attrs.get('produit') if 'produit' in attrs else getattr(
            self.instance, 'produit', None)
        designation = attrs.get('designation') if 'designation' in attrs else (
            getattr(self.instance, 'designation', None))
        if produit is None and not (designation or '').strip():
            raise serializers.ValidationError(
                {'designation': 'Indiquez un produit ou une designation.'})
        return attrs


class ColisSerializer(serializers.ModelSerializer):
    """FG322 - colis de preparation d'un chantier. Reference/societe/`created_by`
    poses COTE SERVEUR ; le statut avance via `controler`/`expedier` (qui posent
    `controle_par`/date). Lignes imbriquees en lecture."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    lignes = ColisLigneSerializer(many=True, read_only=True)

    class Meta:
        model = Colis
        fields = [
            'id', 'reference', 'installation', 'statut', 'statut_display',
            'poids_kg', 'note', 'lignes', 'controle_par', 'date_controle',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'controle_par', 'date_controle',
            'created_by', 'date_creation', 'date_modification',
        ]


class SerieEntrepotSerializer(serializers.ModelSerializer):
    """FG323 - n0 de serie suivi en entrepot. La societe et `created_by` sont
    poses COTE SERVEUR ; le statut avance via les actions `reserver`/`sortir`
    (ou par mise a jour du `bin`)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    bin_code = serializers.CharField(
        source='bin.code', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)

    class Meta:
        model = SerieEntrepot
        fields = [
            'id', 'produit', 'produit_nom', 'numero_serie', 'emplacement',
            'bin', 'bin_code', 'statut', 'statut_display', 'installation',
            'reference_reception', 'note',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'statut', 'created_by', 'date_creation', 'date_modification',
        ]

    def validate_numero_serie(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le numero de serie est requis.')
        return value


class ComptageLigneSerializer(serializers.ModelSerializer):
    """FG324 - ligne de comptage (SKU + theorique snapshot + comptee + ecart)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    ecart = serializers.IntegerField(read_only=True)

    class Meta:
        model = ComptageLigne
        fields = [
            'id', 'session', 'produit', 'produit_nom', 'designation',
            'quantite_theorique', 'quantite_comptee', 'compte', 'ecart',
        ]
        read_only_fields = ['session', 'quantite_theorique']


class SessionComptageSerializer(serializers.ModelSerializer):
    """FG324 - session de comptage tournant. Reference/societe/`created_by`
    poses COTE SERVEUR ; le statut avance via `demarrer`/`terminer` ; les
    lignes sont generees serveur (action `generer-lignes`)."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    classe_abc_display = serializers.CharField(
        source='get_classe_abc_display', read_only=True, default=None)
    lignes = ComptageLigneSerializer(many=True, read_only=True)

    class Meta:
        model = SessionComptage
        fields = [
            'id', 'reference', 'intitule', 'emplacement', 'classe_abc',
            'classe_abc_display', 'statut', 'statut_display', 'date_planifiee',
            'note', 'lignes', 'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'created_by',
            'date_creation', 'date_modification',
        ]


class DemandeTransfertSerializer(serializers.ModelSerializer):
    """FG325 - demande de transfert inter-emplacements. Reference/societe/
    `created_by` poses COTE SERVEUR ; le statut et les champs d'approbation/
    execution avancent via les actions `approuver`/`refuser`/`executer`."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    source_nom = serializers.CharField(
        source='source.nom', read_only=True, default=None)
    destination_nom = serializers.CharField(
        source='destination.nom', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)

    class Meta:
        model = DemandeTransfert
        fields = [
            'id', 'reference', 'produit', 'produit_nom', 'source', 'source_nom',
            'destination', 'destination_nom', 'quantite', 'statut',
            'statut_display', 'motif', 'motif_refus', 'approuve_par',
            'date_approbation', 'date_execution',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'motif_refus', 'approuve_par',
            'date_approbation', 'date_execution', 'created_by',
            'date_creation', 'date_modification',
        ]

    def validate_quantite(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError(
                'La quantite demandee doit etre strictement positive.')
        return value

    def validate(self, attrs):
        source = attrs.get('source') if 'source' in attrs else getattr(
            self.instance, 'source', None)
        destination = attrs.get('destination') if 'destination' in attrs else (
            getattr(self.instance, 'destination', None))
        if source is not None and destination is not None and (
                source == destination):
            raise serializers.ValidationError(
                {'destination': 'La destination doit differer de la source.'})
        return attrs


class RegleReapproSerializer(serializers.ModelSerializer):
    """FG326 - regle min/max de reapprovisionnement. La societe et `created_by`
    sont poses COTE SERVEUR. `seuil_max` doit etre >= `seuil_min`."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    emplacement_cible_nom = serializers.CharField(
        source='emplacement_cible.nom', read_only=True, default=None)
    emplacement_source_nom = serializers.CharField(
        source='emplacement_source.nom', read_only=True, default=None)

    class Meta:
        model = RegleReappro
        fields = [
            'id', 'produit', 'produit_nom', 'emplacement_cible',
            'emplacement_cible_nom', 'emplacement_source',
            'emplacement_source_nom', 'seuil_min', 'seuil_max', 'active',
            'note', 'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'created_by', 'date_creation', 'date_modification',
        ]

    def validate(self, attrs):
        seuil_min = attrs.get('seuil_min') if 'seuil_min' in attrs else getattr(
            self.instance, 'seuil_min', 0)
        seuil_max = attrs.get('seuil_max') if 'seuil_max' in attrs else getattr(
            self.instance, 'seuil_max', 0)
        if seuil_max < seuil_min:
            raise serializers.ValidationError(
                {'seuil_max': 'Le seuil max doit etre >= au seuil min.'})
        return attrs


class MaterielConsigneSerializer(serializers.ModelSerializer):
    """FG327 - materiel consigne retournable. Societe/`created_by` poses COTE
    SERVEUR ; le statut et la trace de retour avancent via l'action `retourner`.
    `caution_totale` est derivee (INTERNE)."""
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True, default=None)
    type_materiel_display = serializers.CharField(
        source='get_type_materiel_display', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    caution_totale = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = MaterielConsigne
        fields = [
            'id', 'designation', 'type_materiel', 'type_materiel_display',
            'fournisseur', 'fournisseur_nom', 'quantite', 'caution_unitaire',
            'caution_totale', 'statut', 'statut_display', 'reference_externe',
            'date_reception', 'date_retour', 'note', 'retourne_par',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'statut', 'date_retour', 'retourne_par', 'created_by',
            'date_creation', 'date_modification',
        ]

    def validate_designation(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('La designation est requise.')
        return value


class KitComposantSerializer(serializers.ModelSerializer):
    """FG328 - composant de la nomenclature d'un kit."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)

    class Meta:
        model = KitComposant
        fields = [
            'id', 'kit', 'produit', 'produit_nom', 'designation', 'quantite',
            'taux_perte_pct',
        ]

    def validate(self, attrs):
        produit = attrs.get('produit') if 'produit' in attrs else getattr(
            self.instance, 'produit', None)
        designation = attrs.get('designation') if 'designation' in attrs else (
            getattr(self.instance, 'designation', None))
        if produit is None and not (designation or '').strip():
            raise serializers.ValidationError(
                {'designation': 'Indiquez un produit ou une designation.'})
        return attrs


class KitSerializer(serializers.ModelSerializer):
    """FG328 - definition d'un kit (article compose + nomenclature). Societe et
    `created_by` poses COTE SERVEUR. Les composants sont imbriques en lecture."""
    produit_compose_nom = serializers.CharField(
        source='produit_compose.nom', read_only=True, default=None)
    composants = KitComposantSerializer(many=True, read_only=True)

    class Meta:
        model = Kit
        fields = [
            'id', 'nom', 'reference_interne', 'produit_compose',
            'produit_compose_nom', 'active', 'note', 'composants',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'created_by', 'date_creation', 'date_modification',
        ]

    def validate_nom(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le nom du kit est requis.')
        return value


class RevisionKitSerializer(serializers.ModelSerializer):
    """XMFG18 - revision (snapshot) de la nomenclature d'un kit de
    pre-assemblage. Lecture seule : creees automatiquement cote serveur."""
    user_nom = serializers.SerializerMethodField()

    class Meta:
        model = RevisionKit
        fields = ['id', 'kit', 'numero', 'composition', 'user', 'user_nom',
                  'date_creation']
        read_only_fields = fields

    def get_user_nom(self, obj):
        u = obj.user
        if u is None:
            return None
        return (f'{u.first_name} {u.last_name}'.strip() or u.username)


class OrdreAssemblageLigneSerializer(serializers.ModelSerializer):
    """XMFG6 - ligne de composant PERSONNALISABLE d'un ordre. `origine` posee
    cote serveur (kit vs ajout) ; l'editabilite (planifie uniquement) est
    controlee par la vue."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)

    class Meta:
        model = OrdreAssemblageLigne
        fields = [
            'id', 'ordre', 'produit', 'produit_nom', 'designation',
            'quantite', 'origine',
        ]
        read_only_fields = ['origine']

    def validate(self, attrs):
        produit = attrs.get('produit') if 'produit' in attrs else getattr(
            self.instance, 'produit', None)
        designation = attrs.get('designation') if 'designation' in attrs else (
            getattr(self.instance, 'designation', None))
        if produit is None and not (designation or '').strip():
            raise serializers.ValidationError(
                {'designation': 'Indiquez un produit ou une designation.'})
        return attrs


class OrdreAssemblageSerializer(serializers.ModelSerializer):
    """FG328 - ordre d'assemblage de N kits. Reference/societe/`created_by`
    poses COTE SERVEUR ; le statut avance via `demarrer`/`terminer`/`annuler`."""
    kit_nom = serializers.CharField(
        source='kit.nom', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    responsable_nom = serializers.CharField(
        source='responsable.username', read_only=True, default=None)
    lignes = OrdreAssemblageLigneSerializer(many=True, read_only=True)
    cout_prevu = serializers.SerializerMethodField()
    temps_prevu_min = serializers.SerializerMethodField()
    temps_reel_min = serializers.SerializerMethodField()

    class Meta:
        model = OrdreAssemblage
        fields = [
            'id', 'reference', 'kit', 'kit_nom', 'quantite', 'statut',
            'statut_display', 'note', 'date_terminaison',
            'emplacement_source', 'emplacement_destination',
            'quantite_produite', 'stock_mouvemente',
            'devis', 'chantier',
            'date_prevue', 'responsable', 'responsable_nom',
            'motif_annulation', 'lignes', 'cout_prevu',
            'temps_prevu_min', 'temps_reel_min',
            # XMFG16 — assemblage sous-traité (façon).
            'sous_traitant', 'ordre_sous_traitance',
            # XMFG18 — révision de nomenclature figée à la création.
            'revision_kit_numero',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'date_terminaison', 'created_by',
            'stock_mouvemente', 'motif_annulation',
            'revision_kit_numero',
            'date_creation', 'date_modification',
        ]

    def validate_quantite(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError(
                'La quantite a assembler doit etre strictement positive.')
        return value

    def get_cout_prevu(self, obj):
        from .services import cout_prevu_assemblage
        return str(cout_prevu_assemblage(obj))

    def get_temps_prevu_min(self, obj):
        from .services import totaux_temps_ordre
        return totaux_temps_ordre(obj)['prevu']

    def get_temps_reel_min(self, obj):
        from .services import totaux_temps_ordre
        return totaux_temps_ordre(obj)['reel']


class OrdreAssemblageActivitySerializer(serializers.ModelSerializer):
    """XMFG4 - chatter de l'ordre d'assemblage."""
    user_nom = serializers.SerializerMethodField()

    class Meta:
        model = OrdreAssemblageActivity
        fields = [
            'id', 'kind', 'field', 'field_label', 'old_value', 'new_value',
            'body', 'user_nom', 'created_at',
        ]

    def get_user_nom(self, obj):
        return getattr(obj.user, 'username', None)


class SerieAssemblageSerializer(serializers.ModelSerializer):
    """XMFG7 - n° de série relevé à la clôture d'un ordre d'assemblage."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)

    class Meta:
        model = SerieAssemblage
        fields = [
            'id', 'ordre', 'produit', 'produit_nom', 'numero_serie', 'role',
            'composite_ref', 'created_by', 'date_creation',
        ]
        read_only_fields = ['created_by', 'date_creation']

    def validate_numero_serie(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Numéro de série requis.')
        return value


class OrdreDemontageLigneSerializer(serializers.ModelSerializer):
    """XMFG12 - ligne de démontage : quantité attendue (BOM) vs récupérée
    (éditable ligne à ligne avant clôture)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)

    class Meta:
        model = OrdreDemontageLigne
        fields = [
            'id', 'ordre', 'produit', 'produit_nom', 'designation',
            'quantite_attendue', 'quantite_recuperee',
        ]
        read_only_fields = ['quantite_attendue']


class ControleQualiteItemModeleSerializer(serializers.ModelSerializer):
    """XMFG13 - item du modèle de checklist QC d'un kit."""

    class Meta:
        model = ControleQualiteItemModele
        fields = [
            'id', 'modele', 'libelle', 'ordre', 'valeur_min', 'valeur_max',
            'unite', 'photo_requise',
        ]


class ControleQualiteModeleSerializer(serializers.ModelSerializer):
    """XMFG13 - modèle de checklist QC par kit. Société posée COTE SERVEUR."""
    items = ControleQualiteItemModeleSerializer(many=True, read_only=True)

    class Meta:
        model = ControleQualiteModele
        fields = ['id', 'kit', 'active', 'items',
                  'date_creation', 'date_modification']
        read_only_fields = ['date_creation', 'date_modification']


class ControleQualiteOrdreSerializer(serializers.ModelSerializer):
    """XMFG13 - exécution d'un item QC pour un ordre d'assemblage donné."""
    item_libelle = serializers.CharField(
        source='item_modele.libelle', read_only=True, default=None)
    valeur_min = serializers.DecimalField(
        source='item_modele.valeur_min', max_digits=12, decimal_places=3,
        read_only=True, default=None)
    valeur_max = serializers.DecimalField(
        source='item_modele.valeur_max', max_digits=12, decimal_places=3,
        read_only=True, default=None)

    class Meta:
        model = ControleQualiteOrdre
        fields = [
            'id', 'ordre', 'item_modele', 'item_libelle', 'resultat',
            'valeur_mesuree', 'valeur_min', 'valeur_max', 'photo',
            'controle_par', 'date_controle',
        ]
        read_only_fields = ['controle_par', 'date_controle']


class OrdreDemontageSerializer(serializers.ModelSerializer):
    """XMFG12 - ordre de démontage (unbuild) : composite → composants.
    Référence/société/`created_by` posés COTE SERVEUR."""
    kit_nom = serializers.CharField(
        source='kit.nom', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    lignes = OrdreDemontageLigneSerializer(many=True, read_only=True)

    class Meta:
        model = OrdreDemontage
        fields = [
            'id', 'reference', 'kit', 'kit_nom', 'quantite', 'statut',
            'statut_display', 'note', 'date_terminaison',
            'emplacement_source', 'emplacement_destination',
            'stock_mouvemente', 'lignes',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'date_terminaison', 'stock_mouvemente',
            'created_by', 'date_creation', 'date_modification',
        ]

    def validate_quantite(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError(
                'La quantite a demonter doit etre strictement positive.')
        return value


class EtapeAssemblageSerializer(serializers.ModelSerializer):
    """XMFG14 - étape de la gamme (mode opératoire) d'un kit."""

    class Meta:
        model = EtapeAssemblage
        fields = [
            'id', 'kit', 'ordre', 'libelle', 'instructions',
            'duree_attendue_min', 'piece_jointe',
        ]

    def validate_libelle(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError("Le libellé de l'étape est requis.")
        return value


class EtapeOrdreSerializer(serializers.ModelSerializer):
    """XMFG14 - étape d'exécution pour un ordre d'assemblage donné."""
    libelle = serializers.CharField(
        source='etape_modele.libelle', read_only=True, default=None)
    instructions = serializers.CharField(
        source='etape_modele.instructions', read_only=True, default=None)
    duree_attendue_min = serializers.IntegerField(
        source='etape_modele.duree_attendue_min', read_only=True, default=None)
    piece_jointe = serializers.PrimaryKeyRelatedField(
        source='etape_modele.piece_jointe', read_only=True, default=None)
    fait_par_nom = serializers.CharField(
        source='fait_par.username', read_only=True, default=None)

    class Meta:
        model = EtapeOrdre
        fields = [
            'id', 'ordre', 'etape_modele', 'libelle', 'instructions',
            'duree_attendue_min', 'piece_jointe', 'fait', 'fait_par',
            'fait_par_nom', 'fait_le', 'duree_reelle_min',
        ]
        read_only_fields = ['fait_par', 'fait_le']


class LivraisonLigneSerializer(serializers.ModelSerializer):
    """FG329 - article d'une livraison (SKU + quantite)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)

    class Meta:
        model = LivraisonLigne
        fields = [
            'id', 'livraison', 'produit', 'produit_nom', 'designation',
            'quantite',
        ]

    def validate(self, attrs):
        produit = attrs.get('produit') if 'produit' in attrs else getattr(
            self.instance, 'produit', None)
        designation = attrs.get('designation') if 'designation' in attrs else (
            getattr(self.instance, 'designation', None))
        if produit is None and not (designation or '').strip():
            raise serializers.ValidationError(
                {'designation': 'Indiquez un produit ou une designation.'})
        return attrs


class LivraisonSerializer(serializers.ModelSerializer):
    """FG329 - livraison planifiee depot -> site. Reference/societe/`created_by`
    poses COTE SERVEUR ; le statut avance via les actions
    `expedier`/`livrer`/`annuler`. Lignes imbriquees en lecture."""
    installation_reference = serializers.CharField(
        source='installation.reference', read_only=True, default=None)
    depot_nom = serializers.CharField(
        source='depot.nom', read_only=True, default=None)
    transporteur_obj_nom = serializers.CharField(
        source='transporteur.nom', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    mode_acheminement_display = serializers.CharField(
        source='get_mode_acheminement_display', read_only=True, default=None)
    lignes = LivraisonLigneSerializer(many=True, read_only=True)

    class Meta:
        model = Livraison
        fields = [
            'id', 'reference', 'installation', 'installation_reference',
            'depot', 'depot_nom', 'transporteur_nom', 'transporteur',
            'transporteur_obj_nom', 'cout_transport', 'mode_acheminement',
            'mode_acheminement_display', 'date_prevue', 'numero_suivi',
            'statut', 'statut_display', 'adresse_site', 'note', 'lignes',
            'stock_mouvemente',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'created_by', 'stock_mouvemente',
            'date_creation', 'date_modification',
        ]


class PreuveLivraisonSerializer(serializers.ModelSerializer):
    """FG330 - preuve de livraison (signature + photo + GPS horodate). La
    societe et `created_by` sont poses COTE SERVEUR. Une seule preuve par
    livraison (OneToOne)."""

    class Meta:
        model = PreuveLivraison
        fields = [
            'id', 'livraison', 'signataire_nom', 'signature_data', 'photo',
            'gps_lat', 'gps_lng', 'horodatage', 'note',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'created_by', 'date_creation', 'date_modification',
        ]


class TransporteurSerializer(serializers.ModelSerializer):
    """FG331 - transporteur (interne/tiers) + tarif de base (INTERNE). La
    societe et `created_by` sont poses COTE SERVEUR."""
    type_transporteur_display = serializers.CharField(
        source='get_type_transporteur_display', read_only=True, default=None)

    class Meta:
        model = Transporteur
        fields = [
            'id', 'nom', 'type_transporteur', 'type_transporteur_display',
            'contact', 'telephone', 'tarif_base', 'active', 'note',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'created_by', 'date_creation', 'date_modification',
        ]

    def validate_nom(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le nom du transporteur est requis.')
        return value


class RetourMaterielLigneSerializer(serializers.ModelSerializer):
    """YSTCK4 - ligne d'un retour de materiel chantier (SKU + quantite)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)

    class Meta:
        model = RetourMaterielLigne
        fields = [
            'id', 'retour', 'produit', 'produit_nom', 'designation',
            'quantite', 'stock_applique',
        ]
        read_only_fields = ['stock_applique']


class RetourMaterielSerializer(serializers.ModelSerializer):
    """YSTCK4 - retour de materiel non pose, d'un chantier vers le depot.
    Societe/`created_by` poses COTE SERVEUR ; le statut avance via l'action
    `valider`. Lignes imbriquees en lecture."""
    installation_reference = serializers.CharField(
        source='installation.reference', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    lignes = RetourMaterielLigneSerializer(many=True, read_only=True)

    class Meta:
        model = RetourMateriel
        fields = [
            'id', 'installation', 'installation_reference', 'statut',
            'statut_display', 'note', 'lignes', 'created_by', 'valide_par',
            'valide_le', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'statut', 'created_by', 'valide_par', 'valide_le',
            'date_creation', 'date_modification',
        ]


class RetourLivraisonLigneSerializer(serializers.ModelSerializer):
    """ZSTK8 - ligne d'un retour de livraison (SKU, livre vs retourne)."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)

    class Meta:
        model = RetourLivraisonLigne
        fields = [
            'id', 'retour', 'produit', 'produit_nom', 'designation',
            'quantite_livree', 'quantite_retournee', 'stock_applique',
        ]
        read_only_fields = ['quantite_livree', 'stock_applique']

    def validate(self, attrs):
        instance = self.instance
        qte_livree = attrs.get(
            'quantite_livree',
            getattr(instance, 'quantite_livree', None))
        qte_retournee = attrs.get(
            'quantite_retournee',
            getattr(instance, 'quantite_retournee', 0))
        if qte_livree is not None and qte_retournee > qte_livree:
            raise serializers.ValidationError(
                {'quantite_retournee':
                 'La quantité retournée ne peut pas dépasser la quantité '
                 'livrée.'})
        return attrs


class RetourLivraisonSerializer(serializers.ModelSerializer):
    """ZSTK8 - retour client genere depuis une Livraison livree. Societe/
    `created_by` poses COTE SERVEUR ; le statut avance via l'action
    `valider`. Lignes imbriquees en lecture, pre-remplies a la generation."""
    livraison_reference = serializers.CharField(
        source='livraison.reference', read_only=True, default=None)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    lignes = RetourLivraisonLigneSerializer(many=True, read_only=True)

    class Meta:
        model = RetourLivraison
        fields = [
            'id', 'livraison', 'livraison_reference', 'statut',
            'statut_display', 'motif', 'lignes', 'created_by', 'valide_par',
            'valide_le', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'statut', 'created_by', 'valide_par', 'valide_le',
            'date_creation', 'date_modification',
        ]


class CategorieStockageSerializer(serializers.ModelSerializer):
    """ZSTK9 - categorie de stockage (capacite/compatibilite) posable sur un
    BinLocation. Societe posee COTE SERVEUR."""

    class Meta:
        model = CategorieStockage
        fields = [
            'id', 'nom', 'poids_max_kg', 'qte_max', 'melange_autorise',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def validate_nom(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError(
                'Le nom de la categorie est requis.')
        return value


class RegleRangementSerializer(serializers.ModelSerializer):
    """ZSTK9 - regle de rangement configurable (produit ou categorie produit
    -> casier cible, par priorite). Societe posee COTE SERVEUR."""
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default=None)
    bin_cible_code = serializers.CharField(
        source='bin_cible.code', read_only=True, default=None)

    class Meta:
        model = RegleRangement
        fields = [
            'id', 'produit', 'produit_nom', 'categorie_produit', 'bin_cible',
            'bin_cible_code', 'priorite', 'actif',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['date_creation', 'date_modification']

    def validate(self, attrs):
        produit = attrs.get('produit') if 'produit' in attrs else getattr(
            self.instance, 'produit', None)
        categorie_produit = (
            attrs.get('categorie_produit')
            if 'categorie_produit' in attrs
            else getattr(self.instance, 'categorie_produit', None))
        if produit is None and not (categorie_produit or '').strip():
            raise serializers.ValidationError(
                'Indiquez un produit ou une categorie produit.')
        return attrs


class LotPrelevementSerializer(serializers.ModelSerializer):
    """ZSTK10 - lot de prelevement regroupant plusieurs pick-lists du meme
    depot. Societe/`created_by`/reference poses COTE SERVEUR."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True, default=None)
    operateur_nom = serializers.CharField(
        source='operateur.username', read_only=True, default=None)
    pick_list_ids = serializers.PrimaryKeyRelatedField(
        source='pick_lists', many=True, read_only=True)

    class Meta:
        model = LotPrelevement
        fields = [
            'id', 'reference', 'statut', 'statut_display', 'operateur',
            'operateur_nom', 'pick_list_ids',
            'created_by', 'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'reference', 'statut', 'created_by',
            'date_creation', 'date_modification',
        ]


class GpsConsentRecordSerializer(serializers.ModelSerializer):
    """XFSM23 — trace de consentement GPS (déjà obtenu). company/technicien/
    recorded_by posés côté serveur ; jamais posée/révoquée par le corps client
    mobile — seule une action responsable/admin dédiée révoque."""
    technicien_nom = serializers.CharField(
        source='technicien.username', read_only=True, default=None)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = GpsConsentRecord
        fields = [
            'id', 'technicien', 'technicien_nom', 'consent_ref',
            'consent_recorded_at', 'recorded_by', 'revoked_at',
            'revoked_reason', 'is_active',
        ]
        read_only_fields = [
            'consent_recorded_at', 'recorded_by', 'revoked_at',
            'revoked_reason',
        ]


class PositionTechnicienSerializer(serializers.ModelSerializer):
    """XFSM23 — position GPS live d'un technicien. company/technicien posés
    côté serveur ; ``distance_site_km``/``hors_perimetre`` sont calculés par
    le service (jamais fournis par le client)."""
    technicien_nom = serializers.CharField(
        source='technicien.username', read_only=True, default=None)

    class Meta:
        model = PositionTechnicien
        fields = [
            'id', 'technicien', 'technicien_nom', 'intervention', 'lat',
            'lng', 'accuracy_m', 'captured_at', 'distance_site_km',
            'hors_perimetre',
        ]
        read_only_fields = [
            'company', 'technicien', 'captured_at', 'distance_site_km',
            'hors_perimetre',
        ]


class GeofenceAlertSerializer(serializers.ModelSerializer):
    """XFSM23 — alerte géofence (position hors du rayon attendu du chantier
    pendant une intervention active). Lecture seule côté API — générée
    uniquement par le service ``enregistrer_position``."""
    technicien_nom = serializers.CharField(
        source='technicien.username', read_only=True, default=None)

    class Meta:
        model = GeofenceAlert
        fields = [
            'id', 'intervention', 'technicien', 'technicien_nom', 'position',
            'distance_site_km', 'rayon_attendu_km', 'created_at',
            'acquittee', 'acquittee_par', 'acquittee_le',
        ]
        read_only_fields = [
            'intervention', 'technicien', 'position', 'distance_site_km',
            'rayon_attendu_km', 'created_at',
        ]
