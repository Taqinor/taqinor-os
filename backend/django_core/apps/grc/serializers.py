"""Sérialiseurs du module GRC & Conformité (NTGRC).

Règle commune : ``company`` n'est JAMAIS lue du corps de la requête — elle est
imposée côté serveur par ``CompanyScopedModelViewSet``.
"""
from rest_framework import serializers

from .models import (
    AnalyseImpactDPIA, AttestationPolitique, CadreConformite, ControleInterne,
    DeficienceControle, ExigenceCadre, FluxDonnees,
    IncidentActivity, IncidentSecurite, JournalDestruction, LegalHold,
    ModeleQuestionnaire, PlanTraitementRisque,
    PolitiqueInterne, PolitiqueRetentionObjet,
    PolitiqueVersion, QuestionnaireFournisseur, ReponseQuestionnaire,
    RevueRisque, RisqueEntreprise, SousTraitantRGPD, TestControle,
    ViolationDonnees,
)


class PolitiqueRetentionObjetSerializer(serializers.ModelSerializer):
    """NTGRC4 — durée de conservation d'un type d'objet, par société."""

    type_objet_libelle = serializers.CharField(
        source='get_type_objet_display', read_only=True)
    action_echeance_libelle = serializers.CharField(
        source='get_action_echeance_display', read_only=True)

    class Meta:
        model = PolitiqueRetentionObjet
        fields = [
            'id', 'type_objet', 'type_objet_libelle',
            'duree_conservation_mois',
            'action_echeance', 'action_echeance_libelle', 'actif',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_duree_conservation_mois(self, valeur):
        if valeur is None or int(valeur) < 1:
            raise serializers.ValidationError(
                'La durée de conservation doit valoir au moins 1 mois.')
        return valeur


class JournalDestructionSerializer(serializers.ModelSerializer):
    """NTGRC5 — ligne IMMUABLE du journal de destruction.

    Tout est en lecture seule sauf à la création : une ligne de journal ne se
    réécrit pas. ``company`` est imposée côté serveur.
    """

    action_libelle = serializers.CharField(
        source='get_action_display', read_only=True)

    class Meta:
        model = JournalDestruction
        fields = [
            'id', 'type_objet', 'objet_ref', 'action', 'action_libelle',
            'politique_ref', 'demande_droit_ref', 'executee_par', 'motif',
            'empreinte_avant', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'executee_par']


class ViolationDonneesSerializer(serializers.ModelSerializer):
    """NTGRC6 — violation de données personnelles (registre réglementaire).

    ``reference`` et ``date_echeance_72h`` sont posées CÔTÉ SERVEUR : la
    première par la numérotation race-safe, la seconde par le modèle à la
    création (détection + 72 h). Aucune des deux n'est lue du corps.
    """

    nature_libelle = serializers.CharField(
        source='get_nature_display', read_only=True)
    gravite_libelle = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)
    echeance_72h_depassee = serializers.SerializerMethodField()

    class Meta:
        model = ViolationDonnees
        fields = [
            'id', 'reference', 'date_detection', 'date_incident',
            'nature', 'nature_libelle', 'categories_donnees',
            'nombre_personnes_estime', 'gravite', 'gravite_libelle',
            'risque_personnes', 'mesures_prises',
            'notification_cndp_requise', 'date_notification_cndp',
            'date_echeance_72h', 'echeance_72h_depassee',
            'personnes_notifiees', 'statut', 'statut_libelle',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'reference', 'date_echeance_72h', 'statut',
            # La notification CNDP s'enregistre par l'action dédiée
            # `notifier-cndp/` (qui pose la date ET le statut ensemble) —
            # jamais par une écriture de champ qui laisserait le statut mentir.
            'date_notification_cndp',
            'created_at', 'updated_at',
        ]

    def get_echeance_72h_depassee(self, obj):
        """Le délai légal est-il dépassé sans notification ? (lecture seule)"""
        from django.utils import timezone

        if not obj.notification_cndp_requise or obj.date_notification_cndp:
            return False
        if obj.date_echeance_72h is None:
            return False
        return obj.date_echeance_72h < timezone.now()

    def validate(self, attrs):
        """Contrôles de cohérence — le message NOMME le champ fautif."""
        detection = attrs.get(
            'date_detection',
            getattr(self.instance, 'date_detection', None))
        incident = attrs.get(
            'date_incident', getattr(self.instance, 'date_incident', None))
        if detection and incident and incident > detection:
            raise serializers.ValidationError({
                'date_incident': "L'incident ne peut pas être postérieur à sa "
                                 'détection.'})
        return attrs


class LegalHoldSerializer(serializers.ModelSerializer):
    """NTGRC8 — mise sous séquestre transverse (legal hold)."""

    motif_libelle = serializers.CharField(
        source='get_motif_display', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = LegalHold
        fields = [
            'id', 'nom', 'motif', 'motif_libelle', 'perimetre',
            'date_debut', 'date_fin', 'statut', 'statut_libelle',
            'demandeur', 'base_juridique', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'statut', 'created_at', 'updated_at']

    def validate_perimetre(self, valeur):
        """Le périmètre est une LISTE de ``{type_objet, filtre}``.

        Un périmètre mal formé est refusé à la saisie plutôt que d'être
        silencieusement ignoré à la résolution : un séquestre qui ne gèle rien
        sans le dire est pire que pas de séquestre du tout.
        """
        if valeur in (None, ''):
            return []
        if not isinstance(valeur, list):
            raise serializers.ValidationError(
                'Le périmètre doit être une liste de {type_objet, filtre}.')
        for entree in valeur:
            if not isinstance(entree, dict) or not (
                    entree.get('type_objet') or '').strip():
                raise serializers.ValidationError(
                    'Chaque entrée du périmètre doit porter un '
                    '« type_objet » non vide.')
        return valeur

    def validate(self, attrs):
        debut = attrs.get('date_debut',
                          getattr(self.instance, 'date_debut', None))
        fin = attrs.get('date_fin', getattr(self.instance, 'date_fin', None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError({
                'date_fin': 'La date de fin ne peut pas précéder la date de '
                            'début.'})
        return attrs


class RisqueEntrepriseSerializer(serializers.ModelSerializer):
    """NTGRC13 — risque d'entreprise (ERM), cotations inhérente et résiduelle.

    Les deux criticités sont CALCULÉES côté serveur (probabilité × impact) :
    exposées en lecture, jamais saisies — une criticité saisie à la main finit
    toujours par contredire ses deux facteurs.
    """

    categorie_libelle = serializers.CharField(
        source='get_categorie_display', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = RisqueEntreprise
        fields = [
            'id', 'reference', 'titre', 'categorie', 'categorie_libelle',
            'description', 'proprietaire',
            'probabilite', 'impact', 'criticite_inherente',
            'reponse',
            'probabilite_residuelle', 'impact_residuel',
            'criticite_residuelle',
            'statut', 'statut_libelle', 'date_revue_prevue',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'reference', 'criticite_inherente', 'criticite_residuelle',
            'created_at', 'updated_at',
        ]

    def _borner(self, champ, valeur):
        mini, maxi = RisqueEntreprise.ECHELLE_MIN, RisqueEntreprise.ECHELLE_MAX
        if valeur is None:
            return valeur
        if not (mini <= int(valeur) <= maxi):
            raise serializers.ValidationError({
                champ: f'La cotation doit valoir entre {mini} et {maxi}.'})
        return valeur

    def validate(self, attrs):
        """Les cotations restent dans la grille — le message nomme le champ."""
        for champ in ('probabilite', 'impact', 'probabilite_residuelle',
                      'impact_residuel'):
            if champ in attrs:
                self._borner(champ, attrs[champ])
        return attrs


class PlanTraitementRisqueSerializer(serializers.ModelSerializer):
    """NTGRC14 — action de traitement d'un risque + son suivi.

    Le risque lié est restreint à la société de l'appelant : un plan ne peut
    jamais pointer le risque d'une autre société (défense en profondeur
    derrière le scoping du viewset).
    """

    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)
    risque_reference = serializers.CharField(
        source='risque.reference', read_only=True)
    en_retard = serializers.SerializerMethodField()

    class Meta:
        model = PlanTraitementRisque
        fields = [
            'id', 'risque', 'risque_reference', 'action', 'responsable',
            'echeance', 'statut', 'statut_libelle', 'cout_estime',
            'avancement_pct', 'en_retard', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_en_retard(self, obj):
        return obj.est_en_retard()

    def get_fields(self):
        fields = super().get_fields()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if company is not None and 'risque' in fields:
            fields['risque'].queryset = RisqueEntreprise.objects.filter(
                company=company)
        return fields

    def validate_avancement_pct(self, valeur):
        if valeur is None:
            return 0
        if not (0 <= int(valeur) <= 100):
            raise serializers.ValidationError(
                "L'avancement doit valoir entre 0 et 100 %.")
        return valeur


class RevueRisqueSerializer(serializers.ModelSerializer):
    """NTGRC15 — revue périodique d'un risque (journal + cadence)."""

    decision_libelle = serializers.CharField(
        source='get_decision_display', read_only=True)
    risque_reference = serializers.CharField(
        source='risque.reference', read_only=True)

    class Meta:
        model = RevueRisque
        fields = [
            'id', 'risque', 'risque_reference', 'date_revue', 'revu_par',
            'decision', 'decision_libelle', 'commentaire', 'prochaine_revue',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_fields(self):
        fields = super().get_fields()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if company is not None and 'risque' in fields:
            fields['risque'].queryset = RisqueEntreprise.objects.filter(
                company=company)
        return fields

    def validate(self, attrs):
        revue = attrs.get('date_revue',
                          getattr(self.instance, 'date_revue', None))
        prochaine = attrs.get(
            'prochaine_revue', getattr(self.instance, 'prochaine_revue', None))
        if revue and prochaine and prochaine <= revue:
            raise serializers.ValidationError({
                'prochaine_revue': 'La prochaine revue doit être postérieure '
                                   'à celle qu\'on enregistre.'})
        return attrs


class ControleInterneSerializer(serializers.ModelSerializer):
    """NTGRC16 — contrôle interne de la bibliothèque (SOX-lite)."""

    domaine_libelle = serializers.CharField(
        source='get_domaine_display', read_only=True)
    type_libelle = serializers.CharField(
        source='get_type_display', read_only=True)
    frequence_libelle = serializers.CharField(
        source='get_frequence_display', read_only=True)

    class Meta:
        model = ControleInterne
        fields = [
            'id', 'code', 'intitule', 'objectif',
            'domaine', 'domaine_libelle', 'type', 'type_libelle',
            'frequence', 'frequence_libelle', 'proprietaire',
            'reference_cadre', 'actif', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_code(self, valeur):
        valeur = (valeur or '').strip()
        if not valeur:
            raise serializers.ValidationError(
                'Le code du contrôle est obligatoire.')
        return valeur


class TestControleSerializer(serializers.ModelSerializer):
    """NTGRC17 — exécution d'un contrôle interne + sa preuve.

    ``risque_ouvert`` est en LECTURE SEULE : il est posé par le service quand
    le test conclut à une déficience, jamais choisi par l'appelant.
    """

    resultat_libelle = serializers.CharField(
        source='get_resultat_display', read_only=True)
    controle_code = serializers.CharField(
        source='controle.code', read_only=True)

    class Meta:
        model = TestControle
        fields = [
            'id', 'controle', 'controle_code', 'date_prevue', 'date_realisee',
            'testeur', 'resultat', 'resultat_libelle', 'echantillon_taille',
            'conclusion', 'piece_preuve_key', 'statut', 'risque_ouvert',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'risque_ouvert', 'created_at', 'updated_at']

    def get_fields(self):
        fields = super().get_fields()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if company is not None and 'controle' in fields:
            fields['controle'].queryset = ControleInterne.objects.filter(
                company=company)
        return fields

    def validate(self, attrs):
        """Un résultat exige la date à laquelle il a été constaté."""
        resultat = attrs.get(
            'resultat', getattr(self.instance, 'resultat', None))
        realisee = attrs.get(
            'date_realisee', getattr(self.instance, 'date_realisee', None))
        if resultat in (TestControle.RESULTAT_EFFICACE,
                        TestControle.RESULTAT_DEFICIENT) and not realisee:
            raise serializers.ValidationError({
                'date_realisee': 'Indiquez la date à laquelle le test a été '
                                 'réalisé.'})
        return attrs


class DeficienceControleSerializer(serializers.ModelSerializer):
    """NTGRC18 — constat de déficience + liens risque / CAPA QHSE.

    ``qhse_capa_ref`` et ``risque_entreprise_ref`` sont des identifiants
    TEXTE : `grc` n'importe jamais les modèles d'une autre app. Les deux sont
    VÉRIFIÉS comme appartenant à la société de l'appelant avant d'être
    acceptés — une référence texte non validée serait une porte inter-tenant.
    """

    gravite_libelle = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = DeficienceControle
        fields = [
            'id', 'test_controle', 'gravite', 'gravite_libelle',
            'description', 'remediation', 'responsable', 'echeance',
            'statut', 'statut_libelle', 'risque_entreprise_ref',
            'qhse_capa_ref', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_fields(self):
        fields = super().get_fields()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if company is not None and 'test_controle' in fields:
            fields['test_controle'].queryset = TestControle.objects.filter(
                company=company)
        return fields

    def _company(self):
        requete = self.context.get('request')
        return getattr(getattr(requete, 'user', None), 'company', None)

    def validate_risque_entreprise_ref(self, valeur):
        valeur = (valeur or '').strip()
        company = self._company()
        if not valeur or company is None:
            return valeur
        try:
            risque_id = int(valeur)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                'La référence du risque doit être un identifiant numérique.')
        if not RisqueEntreprise.objects.filter(
                company=company, pk=risque_id).exists():
            raise serializers.ValidationError(
                "Ce risque d'entreprise n'existe pas pour votre société.")
        return valeur

    def validate_qhse_capa_ref(self, valeur):
        """Vérifie le CAPA via le SELECTOR de `qhse` — aucun import de modèle."""
        valeur = (valeur or '').strip()
        company = self._company()
        if not valeur or company is None:
            return valeur
        from apps.qhse.selectors import capa_ids_de_societe

        try:
            capa_id = int(valeur)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                'La référence du CAPA doit être un identifiant numérique.')
        if capa_id not in set(capa_ids_de_societe(company)):
            raise serializers.ValidationError(
                "Ce CAPA QHSE n'existe pas pour votre société.")
        return valeur

    def validate(self, attrs):
        """Une déficience MAJEURE doit dire qui remédie et pour quand."""
        gravite = attrs.get('gravite',
                            getattr(self.instance, 'gravite', None))
        if gravite == DeficienceControle.GRAVITE_MAJEURE:
            responsable = attrs.get(
                'responsable', getattr(self.instance, 'responsable', ''))
            if not (responsable or '').strip():
                raise serializers.ValidationError({
                    'responsable': 'Une déficience majeure doit nommer un '
                                   'responsable de la remédiation.'})
        return attrs


class PolitiqueVersionSerializer(serializers.ModelSerializer):
    """NTGRC19 — snapshot IMMUABLE d'une politique publiée (lecture seule)."""

    class Meta:
        model = PolitiqueVersion
        fields = ['id', 'politique', 'numero', 'contenu', 'auteur',
                  'publiee_le', 'created_at']
        read_only_fields = fields


class PolitiqueInterneSerializer(serializers.ModelSerializer):
    """NTGRC19 — politique interne versionnée.

    ``version``, ``statut`` et ``date_publication`` sont posés par l'action
    ``publier/`` : les rendre écrivables permettrait d'annoncer une v3 sans
    qu'aucune v3 ne soit figée nulle part.
    """

    categorie_libelle = serializers.CharField(
        source='get_categorie_display', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)
    nombre_versions = serializers.SerializerMethodField()

    class Meta:
        model = PolitiqueInterne
        fields = [
            'id', 'titre', 'categorie', 'categorie_libelle', 'contenu',
            'version', 'statut', 'statut_libelle', 'date_publication',
            'proprietaire', 'cible', 'cible_valeur', 'nombre_versions',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'version', 'statut', 'date_publication',
            'created_at', 'updated_at',
        ]

    def get_nombre_versions(self, obj):
        return obj.versions.count()

    def validate(self, attrs):
        """Une cible « rôle » ou « département » doit dire LAQUELLE."""
        cible = attrs.get('cible', getattr(self.instance, 'cible', None))
        valeur = attrs.get(
            'cible_valeur', getattr(self.instance, 'cible_valeur', ''))
        if cible in (PolitiqueInterne.CIBLE_ROLE,
                     PolitiqueInterne.CIBLE_DEPARTEMENT) and not (
                valeur or '').strip():
            raise serializers.ValidationError({
                'cible_valeur': 'Précisez le rôle ou le département visé.'})
        return attrs


class AttestationPolitiqueSerializer(serializers.ModelSerializer):
    """NTGRC20 — attestation de lecture d'une politique publiée.

    ``version_attestee``, ``date_attestation`` et ``preuve`` sont en LECTURE
    SEULE : ils sont posés côté serveur. Une preuve que l'appelant peut écrire
    lui-même n'atteste de rien.
    """

    politique_titre = serializers.CharField(
        source='politique.titre', read_only=True)

    class Meta:
        model = AttestationPolitique
        fields = [
            'id', 'politique', 'politique_titre', 'version_attestee',
            'employe_ref', 'attestant_nom', 'nom_saisi', 'date_attestation',
            'preuve', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'version_attestee', 'date_attestation', 'preuve',
            'created_at', 'updated_at',
        ]

    def get_fields(self):
        fields = super().get_fields()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if company is not None and 'politique' in fields:
            fields['politique'].queryset = PolitiqueInterne.objects.filter(
                company=company)
        return fields

    def validate_nom_saisi(self, valeur):
        valeur = (valeur or '').strip()
        if not valeur:
            raise serializers.ValidationError(
                'Saisissez le nom de la personne qui atteste (loi 53-05).')
        return valeur

    def validate_employe_ref(self, valeur):
        """Le dossier employé doit appartenir à la société de l'appelant."""
        valeur = str(valeur or '').strip()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if not valeur or company is None:
            return valeur
        from apps.rh.selectors import dossier_appartient_societe

        try:
            employe_id = int(valeur)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                'La référence employé doit être un identifiant numérique.')
        if not dossier_appartient_societe(company, employe_id):
            raise serializers.ValidationError(
                "Ce dossier employé n'existe pas pour votre société.")
        return valeur


class ReponseQuestionnaireSerializer(serializers.ModelSerializer):
    """NTGRC22 — une question du questionnaire et la réponse du fournisseur."""

    class Meta:
        model = ReponseQuestionnaire
        fields = [
            'id', 'questionnaire', 'ordre', 'question', 'obligatoire',
            'reponse', 'conforme', 'commentaire', 'piece_key',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_fields(self):
        fields = super().get_fields()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if company is not None and 'questionnaire' in fields:
            fields['questionnaire'].queryset = (
                QuestionnaireFournisseur.objects.filter(company=company))
        return fields

    def validate_question(self, valeur):
        valeur = (valeur or '').strip()
        if not valeur:
            raise serializers.ValidationError(
                "L'intitulé de la question est obligatoire.")
        return valeur


class QuestionnaireFournisseurSerializer(serializers.ModelSerializer):
    """NTGRC22 — questionnaire de conformité adressé à un fournisseur.

    ``statut`` et ``score`` sont en LECTURE SEULE : le premier bouge par le
    service de transition (ou automatiquement quand toutes les réponses sont
    renseignées), le second se recalcule — les laisser écrivables permettrait
    d'annoncer « validé, 100 % » sur un questionnaire vide.
    """

    type_libelle = serializers.CharField(
        source='get_type_display', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)
    nombre_questions = serializers.SerializerMethodField()
    nombre_reponses = serializers.SerializerMethodField()

    class Meta:
        model = QuestionnaireFournisseur
        fields = [
            'id', 'fournisseur_ref', 'type', 'type_libelle', 'statut',
            'statut_libelle', 'date_envoi', 'date_echeance', 'score',
            'evaluateur', 'modele_ref', 'nombre_questions', 'nombre_reponses',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'score', 'modele_ref', 'created_at', 'updated_at']

    def get_nombre_questions(self, obj):
        return obj.reponses.count()

    def get_nombre_reponses(self, obj):
        return sum(1 for r in obj.reponses.all() if r.est_repondue)

    def validate_fournisseur_ref(self, valeur):
        """Le fournisseur doit appartenir à la société de l'appelant.

        Vérifié par le SELECTOR de ``stock`` — aucun import de ses modèles.
        Une référence texte non validée serait une porte inter-tenant.
        """
        valeur = str(valeur or '').strip()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if not valeur or company is None:
            return valeur
        from apps.stock.selectors import get_fournisseur_by_id

        try:
            fournisseur_id = int(valeur)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                'La référence fournisseur doit être un identifiant '
                'numérique.')
        if get_fournisseur_by_id(company, fournisseur_id) is None:
            raise serializers.ValidationError(
                "Ce fournisseur n'existe pas pour votre société.")
        return valeur

    def validate(self, attrs):
        envoi = attrs.get('date_envoi',
                          getattr(self.instance, 'date_envoi', None))
        echeance = attrs.get('date_echeance',
                             getattr(self.instance, 'date_echeance', None))
        if envoi and echeance and echeance < envoi:
            raise serializers.ValidationError({
                'date_echeance': "L'échéance ne peut pas précéder la date "
                                 "d'envoi."})
        return attrs


class ModeleQuestionnaireSerializer(serializers.ModelSerializer):
    """NTGRC23 — trame réutilisable d'un questionnaire fournisseur."""

    type_libelle = serializers.CharField(
        source='get_type_display', read_only=True)
    nombre_questions = serializers.SerializerMethodField()

    class Meta:
        model = ModeleQuestionnaire
        fields = [
            'id', 'code', 'nom', 'type', 'type_libelle', 'questions',
            'nombre_questions', 'actif', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_nombre_questions(self, obj):
        from .services import questions_du_modele

        return len(questions_du_modele(obj))

    def validate_code(self, valeur):
        valeur = (valeur or '').strip()
        if not valeur:
            raise serializers.ValidationError(
                'Le code du modèle est obligatoire (clé stable du seed).')
        return valeur

    def validate_questions(self, valeur):
        """Une trame sans aucune question exploitable n'est pas une trame."""
        if valeur in (None, ''):
            return []
        if not isinstance(valeur, list):
            raise serializers.ValidationError(
                'Les questions doivent être une LISTE de '
                '{intitule, obligatoire, type_reponse}.')
        for entree in valeur:
            if isinstance(entree, str) and entree.strip():
                continue
            if isinstance(entree, dict) and str(
                    entree.get('intitule') or '').strip():
                continue
            raise serializers.ValidationError(
                'Chaque question doit porter un « intitule » non vide.')
        return valeur


class IncidentSecuriteSerializer(serializers.ModelSerializer):
    """NTGRC25 — incident de sécurité (distinct d'une violation de données).

    ``reference``, ``statut`` et ``violation_donnees_ref`` sont en LECTURE
    SEULE : la première vient de la numérotation race-safe, le deuxième bouge
    par ``changer-statut/`` (garde de transition), le troisième est posé par
    l'escalade — l'écrire à la main ferait pointer un incident vers n'importe
    quelle violation.
    """

    type_libelle = serializers.CharField(
        source='get_type_display', read_only=True)
    severite_libelle = serializers.CharField(
        source='get_severite_display', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = IncidentSecurite
        fields = [
            'id', 'reference', 'titre', 'type', 'type_libelle', 'severite',
            'severite_libelle', 'date_detection', 'systemes_touches',
            'description', 'impact', 'statut', 'statut_libelle', 'assigne',
            'violation_donnees_ref', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'reference', 'statut', 'violation_donnees_ref',
            'created_at', 'updated_at',
        ]

    def validate_titre(self, valeur):
        valeur = (valeur or '').strip()
        if not valeur:
            raise serializers.ValidationError(
                "Le titre de l'incident est obligatoire.")
        return valeur

    def validate_systemes_touches(self, valeur):
        if valeur in (None, ''):
            return []
        if not isinstance(valeur, list):
            raise serializers.ValidationError(
                'Les systèmes touchés doivent être une LISTE de libellés.')
        return valeur


class AnalyseImpactDPIASerializer(serializers.ModelSerializer):
    """NTGRC27 — analyse d'impact (AIPD) d'un traitement du registre CNDP.

    ``statut`` et ``date_validation`` sont en LECTURE SEULE : ils bougent
    ENSEMBLE par l'action ``valider/``. Une AIPD qu'on peut déclarer « validée »
    d'un coup de PATCH ne vaut pas mieux qu'une case à cocher.
    """

    risque_residuel_libelle = serializers.CharField(
        source='get_risque_residuel_display', read_only=True)
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = AnalyseImpactDPIA
        fields = [
            'id', 'traitement_ref', 'necessite_dpia', 'critere_declencheur',
            'risques_identifies', 'mesures_attenuation', 'risque_residuel',
            'risque_residuel_libelle', 'avis_dpo', 'statut', 'statut_libelle',
            'date_validation', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'date_validation', 'created_at', 'updated_at']

    def validate_traitement_ref(self, valeur):
        """Le traitement doit appartenir à la société de l'appelant.

        Vérifié via le registre de ``core`` (couche FONDATION) : une référence
        texte non validée serait une porte inter-tenant.
        """
        valeur = str(valeur or '').strip()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if not valeur:
            raise serializers.ValidationError(
                'Indiquez le traitement analysé.')
        if company is None:
            return valeur
        from core.models import RegistreTraitement

        try:
            traitement_id = int(valeur)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                'La référence du traitement doit être un identifiant '
                'numérique.')
        if not RegistreTraitement.objects.filter(
                company=company, pk=traitement_id).exists():
            raise serializers.ValidationError(
                "Ce traitement n'existe pas pour votre société.")
        return valeur

    def validate(self, attrs):
        """Une AIPD déclarée NON nécessaire doit dire POURQUOI."""
        necessite = attrs.get(
            'necessite_dpia', getattr(self.instance, 'necessite_dpia', True))
        avis = attrs.get('avis_dpo', getattr(self.instance, 'avis_dpo', ''))
        if necessite is False and not (avis or '').strip():
            raise serializers.ValidationError({
                'avis_dpo': 'Justifiez pourquoi aucune analyse d\'impact '
                            'n\'est nécessaire.'})
        return attrs


class SousTraitantRGPDSerializer(serializers.ModelSerializer):
    """NTGRC35 — sous-traitant au sens de l'art. 28 RGPD / loi 09-08."""

    niveau_risque_libelle = serializers.CharField(
        source='get_niveau_risque_display', read_only=True)

    class Meta:
        model = SousTraitantRGPD
        fields = [
            'id', 'nom', 'fournisseur_ref', 'finalites',
            'categories_donnees', 'localisation_donnees', 'clause_signee',
            'date_clause', 'questionnaire_ref', 'niveau_risque',
            'niveau_risque_libelle', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _company(self):
        requete = self.context.get('request')
        return getattr(getattr(requete, 'user', None), 'company', None)

    def validate_nom(self, valeur):
        valeur = (valeur or '').strip()
        if not valeur:
            raise serializers.ValidationError(
                'Le nom du sous-traitant est obligatoire.')
        return valeur

    def validate_fournisseur_ref(self, valeur):
        """Vérifié via le SELECTOR de ``stock`` — aucun import de modèle."""
        valeur = str(valeur or '').strip()
        company = self._company()
        if not valeur or company is None:
            return valeur
        from apps.stock.selectors import get_fournisseur_by_id

        try:
            fournisseur_id = int(valeur)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                'La référence fournisseur doit être un identifiant '
                'numérique.')
        if get_fournisseur_by_id(company, fournisseur_id) is None:
            raise serializers.ValidationError(
                "Ce fournisseur n'existe pas pour votre société.")
        return valeur

    def validate_questionnaire_ref(self, valeur):
        """Le questionnaire lié doit appartenir à la société de l'appelant."""
        valeur = str(valeur or '').strip()
        company = self._company()
        if not valeur or company is None:
            return valeur
        try:
            questionnaire_id = int(valeur)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                'La référence du questionnaire doit être un identifiant '
                'numérique.')
        if not QuestionnaireFournisseur.objects.filter(
                company=company, pk=questionnaire_id).exists():
            raise serializers.ValidationError(
                "Ce questionnaire n'existe pas pour votre société.")
        return valeur

    def validate(self, attrs):
        """Une clause déclarée SIGNÉE doit dire QUAND."""
        signee = attrs.get(
            'clause_signee', getattr(self.instance, 'clause_signee', False))
        date_clause = attrs.get(
            'date_clause', getattr(self.instance, 'date_clause', None))
        if signee and date_clause is None:
            raise serializers.ValidationError({
                'date_clause': 'Indiquez la date de signature de la clause.'})
        return attrs


class CadreConformiteSerializer(serializers.ModelSerializer):
    """NTGRC33 — référentiel de conformité suivi par la société."""

    code_libelle = serializers.CharField(
        source='get_code_display', read_only=True)
    couverture = serializers.SerializerMethodField()

    class Meta:
        model = CadreConformite
        fields = ['id', 'code', 'code_libelle', 'intitule', 'actif',
                  'couverture', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_couverture(self, obj):
        from .selectors import taux_couverture

        return taux_couverture(obj.company, obj)


class ExigenceCadreSerializer(serializers.ModelSerializer):
    """NTGRC33 — exigence d'un cadre et le contrôle interne qui la couvre."""

    statut_couverture_libelle = serializers.CharField(
        source='get_statut_couverture_display', read_only=True)
    cadre_code = serializers.CharField(source='cadre.code', read_only=True)

    class Meta:
        model = ExigenceCadre
        fields = ['id', 'cadre', 'cadre_code', 'code_exigence', 'intitule',
                  'controle_ref', 'statut_couverture',
                  'statut_couverture_libelle', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_fields(self):
        fields = super().get_fields()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if company is not None and 'cadre' in fields:
            fields['cadre'].queryset = CadreConformite.objects.filter(
                company=company)
        return fields

    def validate_controle_ref(self, valeur):
        """Le contrôle référencé doit exister DANS la société de l'appelant."""
        valeur = str(valeur or '').strip()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if not valeur or company is None:
            return valeur
        try:
            controle_id = int(valeur)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                'La référence du contrôle doit être un identifiant '
                'numérique.')
        if not ControleInterne.objects.filter(
                company=company, pk=controle_id).exists():
            raise serializers.ValidationError(
                "Ce contrôle interne n'existe pas pour votre société.")
        return valeur

    def validate(self, attrs):
        """Une exigence déclarée COUVERTE doit dire PAR QUOI."""
        statut = attrs.get(
            'statut_couverture',
            getattr(self.instance, 'statut_couverture', None))
        controle = attrs.get(
            'controle_ref', getattr(self.instance, 'controle_ref', ''))
        if statut == ExigenceCadre.COUVERTURE_COUVERT and not (
                controle or '').strip():
            raise serializers.ValidationError({
                'controle_ref': 'Indiquez le contrôle interne qui couvre '
                                'cette exigence.'})
        return attrs


class FluxDonneesSerializer(serializers.ModelSerializer):
    """NTGRC30 — flux de données personnelles (cartographie)."""

    destination_libelle = serializers.CharField(
        source='get_destination_display', read_only=True)
    garanties_libelle = serializers.CharField(
        source='get_garanties_display', read_only=True)

    class Meta:
        model = FluxDonnees
        fields = [
            'id', 'traitement_ref', 'source', 'destination',
            'destination_libelle', 'destinataire', 'categories_donnees',
            'transfert_hors_maroc', 'pays_destination', 'garanties',
            'garanties_libelle', 'volume_estime', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_source(self, valeur):
        valeur = (valeur or '').strip()
        if not valeur:
            raise serializers.ValidationError(
                'Indiquez le système source du flux.')
        return valeur

    def validate_categories_donnees(self, valeur):
        if valeur in (None, ''):
            return []
        if not isinstance(valeur, list):
            raise serializers.ValidationError(
                'Les catégories de données doivent être une LISTE.')
        return valeur

    def validate_traitement_ref(self, valeur):
        """Le traitement, s'il est indiqué, doit être celui de la société."""
        valeur = str(valeur or '').strip()
        requete = self.context.get('request')
        company = getattr(getattr(requete, 'user', None), 'company', None)
        if not valeur or company is None:
            return valeur
        from core.models import RegistreTraitement

        try:
            traitement_id = int(valeur)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                'La référence du traitement doit être un identifiant '
                'numérique.')
        if not RegistreTraitement.objects.filter(
                company=company, pk=traitement_id).exists():
            raise serializers.ValidationError(
                "Ce traitement n'existe pas pour votre société.")
        return valeur

    def validate(self, attrs):
        """Un transfert hors Maroc doit dire OÙ il va."""
        hors = attrs.get(
            'transfert_hors_maroc',
            getattr(self.instance, 'transfert_hors_maroc', False))
        pays = attrs.get(
            'pays_destination',
            getattr(self.instance, 'pays_destination', ''))
        if hors and not (pays or '').strip():
            raise serializers.ValidationError({
                'pays_destination': 'Indiquez le pays de destination du '
                                    'transfert.'})
        return attrs


class IncidentActivitySerializer(serializers.ModelSerializer):
    """NTGRC26 — ligne de chronologie d'un incident (lecture seule).

    Tout est en lecture seule : une ligne de chronologie s'AJOUTE (par
    ``noter/`` ou par le service de transition), elle ne se réécrit pas — un
    journal éditable ne prouve rien.
    """

    type_libelle = serializers.CharField(
        source='get_type_display', read_only=True)

    class Meta:
        model = IncidentActivity
        fields = ['id', 'incident', 'type', 'type_libelle', 'detail',
                  'auteur', 'timestamp', 'created_at']
        read_only_fields = fields
