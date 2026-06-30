"""Sérialiseurs QHSE.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import (
    ActionCorrectivePreventive, AnalyseIncident, Audit, CauseIncident,
    ConsignationLoto, ContactUrgence,
    CritereAudit, DeclarationCnss, EvaluationRisque, GrilleAudit,
    InductionSecurite,
    Incident,
    ItemNotation, LigneEvaluationRisque, NonConformite, NotationFinChantier,
    PermisTravail, PlanInspectionChantier, PlanInspectionModele, PlanUrgence,
    PointControleModele, ProcedureQualite, QhseChatterEntry, ReleveControle,
    ReleveCourbeIV, ReponseCritere, RetourClientQualite, Secouriste,
)


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class NonConformiteSerializer(serializers.ModelSerializer):
    gravite_display = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = NonConformite
        fields = [
            'id', 'reference', 'titre', 'description', 'gravite',
            'gravite_display', 'origine', 'statut', 'statut_display',
            'chantier_id', 'reserve', 'signale_par', 'date_detection',
            'date_creation',
        ]
        read_only_fields = ['reserve', 'signale_par', 'date_creation']


class ActionCorrectivePreventiveSerializer(serializers.ModelSerializer):
    type_action_display = serializers.CharField(
        source='get_type_action_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = ActionCorrectivePreventive
        fields = [
            'id', 'non_conformite', 'type_action', 'type_action_display',
            'description', 'cause_racine', 'responsable', 'echeance',
            'statut', 'statut_display', 'efficace', 'commentaire_verification',
            'date_verification', 'verifiee_par', 'date_creation',
        ]
        read_only_fields = [
            'efficace', 'commentaire_verification', 'date_verification',
            'verifiee_par', 'date_creation',
        ]

    def validate_non_conformite(self, value):
        return _meme_societe(self, value, 'Non-conformité')


class PlanInspectionModeleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanInspectionModele
        fields = [
            'id', 'code', 'nom', 'description', 'actif', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class PointControleModeleSerializer(serializers.ModelSerializer):
    type_releve_display = serializers.CharField(
        source='get_type_releve_display', read_only=True)

    class Meta:
        model = PointControleModele
        fields = [
            'id', 'plan', 'ordre', 'intitule', 'phase', 'type_releve',
            'type_releve_display', 'valeur_min', 'valeur_max', 'hold_point',
            'description', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_plan(self, value):
        return _meme_societe(self, value, "Plan d'inspection")


class PlanInspectionChantierSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    modele_nom = serializers.CharField(source='modele.nom', read_only=True)
    nb_releves = serializers.IntegerField(
        source='releves.count', read_only=True)
    # QHSE6 — gating points d'arrêt : True si aucun point d'arrêt bloquant
    # (relevé absent ou non conforme) n'empêche l'avancement chantier.
    peut_avancer = serializers.SerializerMethodField()
    nb_hold_points_bloquants = serializers.SerializerMethodField()

    class Meta:
        model = PlanInspectionChantier
        fields = [
            'id', 'modele', 'modele_nom', 'chantier_id', 'date_ouverture',
            'statut', 'statut_display', 'nb_releves', 'peut_avancer',
            'nb_hold_points_bloquants', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def _hold_points_status(self, obj):
        # Calcul mémoïsé par instance pour ne pas le refaire deux fois.
        cache = getattr(obj, '_hold_points_status_cache', None)
        if cache is None:
            from .selectors import hold_points_status
            cache = hold_points_status(obj)
            obj._hold_points_status_cache = cache
        return cache

    def get_peut_avancer(self, obj):
        return self._hold_points_status(obj)['peut_avancer']

    def get_nb_hold_points_bloquants(self, obj):
        return self._hold_points_status(obj)['nb_bloquants']

    def validate_modele(self, value):
        return _meme_societe(self, value, "Modèle d'ITP")


class ReleveControleSerializer(serializers.ModelSerializer):
    point_intitule = serializers.CharField(
        source='point.intitule', read_only=True)
    point_phase = serializers.CharField(source='point.phase', read_only=True)
    point_hold_point = serializers.BooleanField(
        source='point.hold_point', read_only=True)
    point_valeur_min = serializers.DecimalField(
        source='point.valeur_min', max_digits=14, decimal_places=4,
        read_only=True)
    point_valeur_max = serializers.DecimalField(
        source='point.valeur_max', max_digits=14, decimal_places=4,
        read_only=True)

    class Meta:
        model = ReleveControle
        fields = [
            'id', 'plan_chantier', 'point', 'point_intitule', 'point_phase',
            'point_hold_point', 'point_valeur_min', 'point_valeur_max',
            'valeur', 'conforme', 'photo_key',
            'date_releve', 'releve_par', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_plan_chantier(self, value):
        return _meme_societe(self, value, "Plan d'inspection chantier")

    def validate_point(self, value):
        return _meme_societe(self, value, 'Point de contrôle')


class ReleveCourbeIVSerializer(serializers.ModelSerializer):
    """Relevé courbe I-V d'un string PV (QHSE7).

    Expose le facteur de forme ``fill_factor`` calculé côté modèle (lecture
    seule) ; ``company`` et ``releve_par`` restent posés côté serveur. Le
    rattachement lâche optionnel ``plan_chantier`` est validé même-société.
    """
    fill_factor = serializers.SerializerMethodField()

    class Meta:
        model = ReleveCourbeIV
        fields = [
            'id', 'chantier_id', 'plan_chantier', 'string_id',
            'voc', 'isc', 'vmpp', 'impp', 'pmpp', 'fill_factor',
            'irradiance', 'temperature_module', 'courbe_points', 'notes',
            'date_releve', 'releve_par', 'date_creation',
        ]
        read_only_fields = ['releve_par', 'date_creation']

    def get_fill_factor(self, obj):
        ff = obj.fill_factor()
        return None if ff is None else str(ff)

    def validate_plan_chantier(self, value):
        return _meme_societe(self, value, "Plan d'inspection chantier")


class QhseChatterEntrySerializer(serializers.ModelSerializer):
    """Entrée de chatter QHSE (QHSE14, lecture seule via l'API)."""
    kind_display = serializers.CharField(
        source='get_kind_display', read_only=True)
    cible_type_display = serializers.CharField(
        source='get_cible_type_display', read_only=True)
    user_nom = serializers.CharField(
        source='user.username', read_only=True, default=None)

    class Meta:
        model = QhseChatterEntry
        fields = [
            'id', 'cible_type', 'cible_type_display', 'cible_id', 'kind',
            'kind_display', 'field', 'field_label', 'old_value', 'new_value',
            'body', 'user', 'user_nom', 'created_at',
        ]
        read_only_fields = fields


class GrilleAuditSerializer(serializers.ModelSerializer):
    """Grille d'audit + critères pondérés (QHSE15)."""
    type_audit_display = serializers.CharField(
        source='get_type_audit_display', read_only=True)
    poids_total = serializers.IntegerField(read_only=True)
    nb_criteres = serializers.IntegerField(
        source='criteres.count', read_only=True)

    class Meta:
        model = GrilleAudit
        fields = [
            'id', 'code', 'nom', 'description', 'type_audit',
            'type_audit_display', 'actif', 'poids_total', 'nb_criteres',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class CritereAuditSerializer(serializers.ModelSerializer):
    """Critère pondéré d'une grille d'audit (QHSE15)."""

    class Meta:
        model = CritereAudit
        fields = [
            'id', 'grille', 'ordre', 'intitule', 'categorie', 'poids',
            'note_max', 'description', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_grille(self, value):
        return _meme_societe(self, value, "Grille d'audit")

    def validate_poids(self, value):
        if value < 1:
            raise serializers.ValidationError('Le poids doit être ≥ 1.')
        return value


class AuditSerializer(serializers.ModelSerializer):
    """Audit (session d'exécution d'une grille — QHSE16)."""
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    grille_nom = serializers.CharField(source='grille.nom', read_only=True)

    class Meta:
        model = Audit
        fields = [
            'id', 'grille', 'grille_nom', 'date_audit', 'auditeur',
            'statut', 'statut_display', 'score', 'notes', 'chantier_id',
            'date_creation',
        ]
        read_only_fields = ['score', 'date_creation']

    def validate_grille(self, value):
        return _meme_societe(self, value, "Grille d'audit")


class ReponseCritereSerializer(serializers.ModelSerializer):
    """Réponse à un critère dans un audit (QHSE16)."""
    resultat_display = serializers.CharField(
        source='get_resultat_display', read_only=True)
    critere_intitule = serializers.CharField(
        source='critere.intitule', read_only=True)
    critere_poids = serializers.IntegerField(
        source='critere.poids', read_only=True)
    critere_categorie = serializers.CharField(
        source='critere.categorie', read_only=True)

    class Meta:
        model = ReponseCritere
        fields = [
            'id', 'audit', 'critere', 'critere_intitule', 'critere_poids',
            'critere_categorie', 'resultat', 'resultat_display', 'note',
            'ncr_id', 'date_creation',
        ]
        read_only_fields = ['ncr_id', 'date_creation']

    def validate_audit(self, value):
        return _meme_societe(self, value, 'Audit')

    def validate_critere(self, value):
        return _meme_societe(self, value, "Critère d'audit")


# ── QHSE17 — Notation fin de chantier ──────────────────────────────────────

class ItemNotationSerializer(serializers.ModelSerializer):
    """Item de notation fin de chantier (QHSE17)."""

    class Meta:
        model = ItemNotation
        fields = [
            'id', 'notation', 'intitule', 'categorie', 'poids',
            'conforme', 'commentaire', 'ordre', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_notation(self, value):
        return _meme_societe(self, value, 'Notation fin de chantier')


class NotationFinChantierSerializer(serializers.ModelSerializer):
    """Notation fin de chantier (QHSE17).

    Expose le ``score`` (calculé), le ``verdict`` et le flag advisory
    ``peut_cloturer`` issu du sélecteur ``chantier_peut_cloturer``.
    """
    verdict_display = serializers.CharField(
        source='get_verdict_display', read_only=True)
    nb_items = serializers.IntegerField(source='items.count', read_only=True)
    peut_cloturer = serializers.SerializerMethodField()

    class Meta:
        model = NotationFinChantier
        fields = [
            'id', 'chantier_id', 'date_notation', 'auteur',
            'score', 'seuil_passage', 'verdict', 'verdict_display',
            'notes', 'nb_items', 'peut_cloturer', 'date_creation',
        ]
        read_only_fields = ['score', 'verdict', 'date_creation']

    def get_peut_cloturer(self, obj):
        from .selectors import chantier_peut_cloturer
        return chantier_peut_cloturer(obj.chantier_id, obj.company)


# ── QHSE18 — Procédure qualité versionnée ──────────────────────────────────

class ProcedureQualiteSerializer(serializers.ModelSerializer):
    """Procédure qualité versionnée (QHSE18).

    ``version`` est posée côté serveur par le service
    ``nouvelle_version_procedure`` (jamais lue du corps de requête) ; ``statut``
    évolue via l'action ``activer``. ``company`` et ``auteur`` sont posés côté
    serveur. ``document_id`` est une référence lâche au document GED.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default=None)

    class Meta:
        model = ProcedureQualite
        fields = [
            'id', 'reference', 'titre', 'version', 'statut', 'statut_display',
            'contenu', 'document_id', 'date_application', 'auteur',
            'auteur_nom', 'date_creation',
        ]
        read_only_fields = [
            'version', 'statut', 'auteur', 'date_application', 'date_creation',
        ]


class RetourClientQualiteSerializer(serializers.ModelSerializer):
    """Retour client de satisfaction qualité (QHSE19).

    ``company`` est posée côté serveur (jamais exposée en écriture).
    ``chantier_id`` / ``client_id`` sont des références lâches par id (jamais
    un import cross-app). ``note_satisfaction`` est bornée à [1, 5].
    """
    canal_display = serializers.CharField(
        source='get_canal_display', read_only=True)

    class Meta:
        model = RetourClientQualite
        fields = [
            'id', 'chantier_id', 'client_id', 'note_satisfaction',
            'commentaire', 'date_retour', 'canal', 'canal_display',
            'traite', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_note_satisfaction(self, value):
        if not (RetourClientQualite.NOTE_MIN
                <= value <= RetourClientQualite.NOTE_MAX):
            raise serializers.ValidationError(
                'La note doit être comprise entre '
                f'{RetourClientQualite.NOTE_MIN} et '
                f'{RetourClientQualite.NOTE_MAX}.')
        return value


# ── QHSE21 — Évaluation des risques (document unique) ───────────────────────

def _valider_niveau(value, label):
    """Garde-fou : un niveau gravité/probabilité doit rester dans [1, 5]."""
    if not (LigneEvaluationRisque.NIVEAU_MIN
            <= value <= LigneEvaluationRisque.NIVEAU_MAX):
        raise serializers.ValidationError(
            f'{label} doit être compris entre '
            f'{LigneEvaluationRisque.NIVEAU_MIN} et '
            f'{LigneEvaluationRisque.NIVEAU_MAX}.')
    return value


class LigneEvaluationRisqueSerializer(serializers.ModelSerializer):
    """Ligne d'une évaluation des risques (QHSE21).

    ``criticite`` est calculée et STOCKÉE côté serveur (gravité × probabilité)
    — exposée en lecture seule, jamais lue du corps. ``company`` est posée côté
    serveur ; le FK ``evaluation`` est validé même-société.
    """

    class Meta:
        model = LigneEvaluationRisque
        fields = [
            'id', 'evaluation', 'poste', 'activite', 'danger',
            'gravite', 'probabilite', 'criticite', 'mesures_prevention',
            'risque_residuel', 'ordre', 'date_creation',
        ]
        read_only_fields = ['criticite', 'date_creation']

    def validate_evaluation(self, value):
        return _meme_societe(self, value, 'Évaluation des risques')

    def validate_gravite(self, value):
        return _valider_niveau(value, 'La gravité')

    def validate_probabilite(self, value):
        return _valider_niveau(value, 'La probabilité')


class EvaluationRisqueSerializer(serializers.ModelSerializer):
    """Évaluation des risques — document unique (QHSE21).

    ``company`` et ``evaluateur`` sont posés côté serveur ; la ``reference`` est
    attribuée côté serveur (jamais lue du corps). Expose le nombre de lignes, la
    criticité maximale et moyenne (résumé), et les lignes imbriquées en lecture.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    evaluateur_nom = serializers.CharField(
        source='evaluateur.username', read_only=True, default=None)
    nb_lignes = serializers.IntegerField(
        source='lignes.count', read_only=True)
    criticite_max = serializers.SerializerMethodField()
    lignes = LigneEvaluationRisqueSerializer(many=True, read_only=True)

    class Meta:
        model = EvaluationRisque
        fields = [
            'id', 'reference', 'titre', 'date_evaluation', 'statut',
            'statut_display', 'chantier_id', 'evaluateur', 'evaluateur_nom',
            'notes', 'nb_lignes', 'criticite_max', 'lignes', 'date_creation',
        ]
        read_only_fields = ['reference', 'evaluateur', 'date_creation']

    def get_criticite_max(self, obj):
        return max(
            (ligne.criticite for ligne in obj.lignes.all()), default=0)


class PermisTravailSerializer(serializers.ModelSerializer):
    """Permis de travail QHSE (QHSE23).

    ``company`` est posée côté serveur ; la ``reference`` est attribuée côté
    serveur (jamais lue du corps). Le ``statut`` n'est piloté que par les actions
    ``valider``/``cloturer`` (lecture seule au CRUD). Valide que ``date_fin`` ne
    précède pas ``date_debut`` quand les deux sont fournies.
    """
    type_permis_display = serializers.CharField(
        source='get_type_permis_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = PermisTravail
        fields = [
            'id', 'reference', 'titre', 'type_permis', 'type_permis_display',
            'statut', 'statut_display', 'chantier_id', 'date_debut',
            'date_fin', 'delivre_par', 'valide_par', 'mesures_prevention',
            'notes', 'date_creation',
        ]
        read_only_fields = ['reference', 'statut', 'date_creation']

    def validate(self, attrs):
        debut = attrs.get('date_debut')
        fin = attrs.get('date_fin')
        if debut is None and self.instance is not None:
            debut = self.instance.date_debut
        if fin is None and self.instance is not None:
            fin = self.instance.date_fin
        if debut is not None and fin is not None and fin < debut:
            raise serializers.ValidationError(
                {'date_fin': 'La fin de validité précède le début.'})
        return attrs


class ConsignationLotoSerializer(serializers.ModelSerializer):
    """Consignation électrique (LOTO) rattachée à un permis (QHSE24).

    ``company`` est posée côté serveur ; la ``reference`` est attribuée côté
    serveur (jamais lue du corps). Le ``statut`` et ``date_deconsignation`` ne
    sont pilotés que par l'action ``deconsigner`` (lecture seule au CRUD). Le
    ``permis`` doit appartenir à la société de l'utilisateur (filtré côté vue).
    """
    permis = serializers.PrimaryKeyRelatedField(
        queryset=PermisTravail.objects.all())
    permis_reference = serializers.CharField(
        source='permis.reference', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = ConsignationLoto
        fields = [
            'id', 'reference', 'permis', 'permis_reference', 'equipement',
            'point_consignation', 'consignateur', 'date_consignation',
            'date_deconsignation', 'cadenas_pose', 'etiquette',
            'verifie_absence_tension', 'statut', 'statut_display', 'notes',
            'date_creation',
        ]
        read_only_fields = [
            'reference', 'statut', 'date_deconsignation', 'date_creation',
        ]

    def validate_permis(self, value):
        return _meme_societe(self, value, 'Permis de travail')


class InductionSecuriteSerializer(serializers.ModelSerializer):
    """Accueil / induction sécurité préalable à l'accès au site (QHSE26).

    ``company`` est posée côté serveur (jamais lue du corps). ``acquittement_le``
    est en lecture seule au CRUD : il n'est posé que par l'action ``acquitter``.
    Le ``employe`` (salarié interne optionnel) doit appartenir à la société de
    l'utilisateur. Pour un sous-traitant externe, ``personne_nom`` (et le plus
    souvent ``entreprise_externe``) suffisent — aucun dossier RH requis.
    """
    employe_nom = serializers.CharField(
        source='employe.__str__', read_only=True)

    class Meta:
        model = InductionSecurite
        fields = [
            'id', 'chantier_id', 'personne_nom', 'est_sous_traitant',
            'entreprise_externe', 'employe', 'employe_nom', 'date_induction',
            'anime_par', 'themes', 'acquittement', 'acquittement_le',
            'validite_jours', 'notes', 'date_creation',
        ]
        read_only_fields = ['acquittement_le', 'date_creation']

    def validate_employe(self, value):
        return _meme_societe(self, value, 'Salarié')


class ContactUrgenceSerializer(serializers.ModelSerializer):
    """Contact d'urgence d'un plan d'urgence (QHSE28).

    ``company`` est posée côté serveur ; le FK ``plan`` est validé même-société.
    """
    type_contact_display = serializers.CharField(
        source='get_type_contact_display', read_only=True)

    class Meta:
        model = ContactUrgence
        fields = [
            'id', 'plan', 'type_contact', 'type_contact_display', 'nom',
            'telephone', 'notes', 'ordre', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_plan(self, value):
        return _meme_societe(self, value, "Plan d'urgence")


class SecouristeSerializer(serializers.ModelSerializer):
    """Secouriste désigné rattaché à un plan d'urgence (QHSE28).

    ``company`` est posée côté serveur ; les FK ``plan`` et ``secouriste``
    (salarié interne optionnel) sont validés même-société. Pour un externe,
    ``nom`` libre suffit — aucun dossier RH requis.
    """
    secouriste_nom = serializers.CharField(
        source='secouriste.__str__', read_only=True)

    class Meta:
        model = Secouriste
        fields = [
            'id', 'plan', 'secouriste', 'secouriste_nom', 'nom', 'telephone',
            'certification', 'validite', 'ordre', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_plan(self, value):
        return _meme_societe(self, value, "Plan d'urgence")

    def validate_secouriste(self, value):
        return _meme_societe(self, value, 'Salarié')


class PlanUrgenceSerializer(serializers.ModelSerializer):
    """Plan d'urgence / premiers secours par chantier (QHSE28).

    ``company`` est posée côté serveur (jamais lue du corps). Expose en lecture
    seule les contacts d'urgence et les secouristes imbriqués, plus leur nombre.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    contacts = ContactUrgenceSerializer(many=True, read_only=True)
    secouristes = SecouristeSerializer(many=True, read_only=True)
    nb_contacts = serializers.IntegerField(
        source='contacts.count', read_only=True)
    nb_secouristes = serializers.IntegerField(
        source='secouristes.count', read_only=True)

    class Meta:
        model = PlanUrgence
        fields = [
            'id', 'chantier_id', 'titre', 'point_rassemblement',
            'point_rassemblement_details', 'hopital_proche',
            'hopital_distance_km', 'hopital_telephone', 'date_revision',
            'statut', 'statut_display', 'notes', 'contacts', 'secouristes',
            'nb_contacts', 'nb_secouristes', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class IncidentSerializer(serializers.ModelSerializer):
    """Registre des incidents HSE (QHSE29).

    ``company`` et ``declare_par`` sont posés côté serveur (jamais lus du corps) ;
    la ``reference`` est attribuée côté serveur (jamais lue du corps). Expose les
    libellés lisibles de ``type_incident``, ``gravite`` et ``statut``.
    """
    type_incident_display = serializers.CharField(
        source='get_type_incident_display', read_only=True)
    gravite_display = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    declare_par_nom = serializers.CharField(
        source='declare_par.username', read_only=True, default=None)

    class Meta:
        model = Incident
        fields = [
            'id', 'reference', 'titre', 'type_incident',
            'type_incident_display', 'gravite', 'gravite_display', 'statut',
            'statut_display', 'chantier_id', 'date_incident', 'description',
            'action_immediate', 'declare_par', 'declare_par_nom',
            'date_creation',
        ]
        read_only_fields = ['reference', 'declare_par', 'date_creation']


class CauseIncidentSerializer(serializers.ModelSerializer):
    """Nœud de l'arbre des causes d'une analyse d'incident (QHSE31).

    ``company`` est posée côté serveur ; les FK ``analyse`` et ``parent`` sont
    validés même-société. ``parent`` doit appartenir à la MÊME analyse (un arbre
    ne mélange pas les analyses).
    """
    type_cause_display = serializers.CharField(
        source='get_type_cause_display', read_only=True)

    class Meta:
        model = CauseIncident
        fields = [
            'id', 'analyse', 'parent', 'type_cause', 'type_cause_display',
            'libelle', 'ordre', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_analyse(self, value):
        return _meme_societe(self, value, "Analyse d'incident")

    def validate_parent(self, value):
        return _meme_societe(self, value, 'Cause parente')

    def validate(self, attrs):
        parent = attrs.get('parent')
        if parent is None and self.instance is not None:
            parent = self.instance.parent
        analyse = attrs.get('analyse')
        if analyse is None and self.instance is not None:
            analyse = self.instance.analyse
        if parent is not None and analyse is not None \
                and parent.analyse_id != analyse.id:
            raise serializers.ValidationError(
                {'parent': 'La cause parente appartient à une autre analyse.'})
        return attrs


class AnalyseIncidentSerializer(serializers.ModelSerializer):
    """Analyse des causes d'un incident — arbre des causes → CAPA (QHSE31).

    ``company`` et ``analyste`` sont posés côté serveur (jamais lus du corps).
    Le FK ``incident`` est validé même-société (et unique : une seule analyse par
    incident). ``non_conformite`` (NCR-pont vers les CAPA) est piloté côté
    serveur par le service ``generer_capa_depuis_analyse`` — lecture seule.
    Expose les libellés lisibles et l'arbre des causes imbriqué en lecture.
    """
    methode_display = serializers.CharField(
        source='get_methode_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    analyste_nom = serializers.CharField(
        source='analyste.username', read_only=True, default=None)
    incident_reference = serializers.CharField(
        source='incident.reference', read_only=True, default=None)
    nb_causes = serializers.IntegerField(
        source='causes.count', read_only=True)
    nb_capa = serializers.SerializerMethodField()
    causes = CauseIncidentSerializer(many=True, read_only=True)

    class Meta:
        model = AnalyseIncident
        fields = [
            'id', 'incident', 'incident_reference', 'methode',
            'methode_display', 'description', 'synthese', 'statut',
            'statut_display', 'date_analyse', 'analyste', 'analyste_nom',
            'non_conformite', 'nb_causes', 'nb_capa', 'causes',
            'date_creation',
        ]
        read_only_fields = [
            'analyste', 'non_conformite', 'date_creation',
        ]

    def validate_incident(self, value):
        return _meme_societe(self, value, 'Incident')

    def get_nb_capa(self, obj):
        if obj.non_conformite_id is None:
            return 0
        return obj.non_conformite.actions.count()


class DeclarationCnssSerializer(serializers.ModelSerializer):
    """Déclaration CNSS d'un accident du travail + échéance légale (QHSE30).

    ``company`` est posée côté serveur (jamais lue du corps). La ``date_limite``
    et le ``statut`` sont calculés côté serveur (``date_accident`` +
    ``delai_jours`` / ``statut_calcule``) — exposés en lecture seule. Le FK
    ``accident_travail`` pointe vers ``rh.AccidentTravail`` (FK-chaîne) : on
    valide qu'il appartient à la même société sans importer le modèle ``rh``.
    Expose aussi un ``statut_courant`` recalculé à la volée (utile si l'échéance
    a basculé depuis le dernier enregistrement).
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    statut_courant = serializers.SerializerMethodField()

    class Meta:
        model = DeclarationCnss
        fields = [
            'id', 'accident_travail', 'date_accident', 'delai_jours',
            'date_limite', 'date_declaration', 'numero_declaration',
            'statut', 'statut_display', 'statut_courant', 'notes',
            'date_creation', 'date_modification',
        ]
        read_only_fields = [
            'date_limite', 'statut', 'date_creation', 'date_modification',
        ]

    def get_statut_courant(self, obj):
        return obj.statut_calcule()

    def validate_accident_travail(self, value):
        """L'accident du travail doit appartenir à la société de l'utilisateur.

        Référence cross-app par FK-chaîne : on lit ``company_id`` directement sur
        l'instance résolue par DRF, sans importer ``rh.models``.
        """
        return _meme_societe(self, value, 'Accident du travail')
