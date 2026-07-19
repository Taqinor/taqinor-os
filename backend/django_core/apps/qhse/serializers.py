"""Sérialiseurs QHSE.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import (
    ActionCorrectivePreventive, AnalyseIncident, AspectEnvironnemental, Audit,
    CauseIncident,
    CodeDefaut,
    ConsignationLoto, ContactUrgence, ControleReception,
    BilanCarbone, BordereauSuiviDechet, ConformiteEnvironnementale,
    CritereAudit, Dechet, DeclarationCnss, DemandeChangement, Derogation,
    EtapeDeclarationAt,
    EvaluationRisque, GrilleAudit,
    ExerciceUrgence,
    InductionSecurite, IndicateurESG,
    LienSignalementPublic,
    LigneBilanCarbone,
    Incident, InspectionSecurite,
    ItemNotation, LigneEvaluationRisque, NonConformite, NotationFinChantier,
    ObservationSecurite,
    PermisTravail, PlanControleReception, PlanInspectionChantier,
    PlanInspectionModele, PlanUrgence,
    PointControleModele, PointControleReception, ProcedureQualite,
    QhseChatterEntry,
    RecyclageModule, ReleveConsommation, ReleveControle,
    ReleveCourbeIV, ReponseCritere, RetourClientQualite,
    RevueVeilleReglementaire, Secouriste,
    SignalementPublic, VeilleReglementaire,
    CheckinSecurite, DemandeActionFournisseur,
)


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class CodeDefautSerializer(serializers.ModelSerializer):
    """Code de défaut normalisé (référentiel, XQHS4). ``company`` posée côté
    serveur."""
    famille_display = serializers.CharField(
        source='get_famille_display', read_only=True)

    class Meta:
        model = CodeDefaut
        fields = [
            'id', 'code', 'libelle', 'famille', 'famille_display', 'actif',
            'date_creation',
        ]
        read_only_fields = ['date_creation']


class NonConformiteSerializer(serializers.ModelSerializer):
    gravite_display = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    disposition_display = serializers.CharField(
        source='get_disposition_display', read_only=True)

    def get_fields(self):
        fields = super().get_fields()
        # XQHS22 — les montants de coût de la non-qualité sont une donnée
        # interne sensible (même règle que `prix_achat`/`marge_pct`) : retirés
        # complètement pour les rôles sans `cout_non_qualite_voir`.
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not getattr(
                user, 'can_view_cout_non_qualite', True):
            fields.pop('cout_disposition', None)
            fields.pop('cout_estime', None)
            fields.pop('cout_reel', None)
        return fields

    class Meta:
        model = NonConformite
        fields = [
            'id', 'reference', 'titre', 'description', 'gravite',
            'gravite_display', 'origine', 'statut', 'statut_display',
            'chantier_id', 'reserve', 'signale_par', 'date_detection',
            # XQHS2 — disposition tracée (qui/quand) + coût interne + retour
            # fournisseur.
            'disposition', 'disposition_display', 'disposition_par',
            'disposition_le', 'cout_disposition', 'fournisseur',
            # XQHS4 — code de défaut normalisé (Pareto).
            'code_defaut',
            # XQHS22 — coût de la non-qualité (interne, gardé par permission).
            'cout_estime', 'cout_reel',
            # XQHS23 — pont SAV (ticket d'origine, FK-chaîne).
            'ticket_sav',
            'date_creation',
        ]
        read_only_fields = [
            'reserve', 'signale_par', 'disposition_par', 'disposition_le',
            'ticket_sav', 'date_creation',
        ]

    def validate_fournisseur(self, value):
        return _meme_societe(self, value, 'Fournisseur')

    def validate_code_defaut(self, value):
        return _meme_societe(self, value, 'Code de défaut')


class ActionCorrectivePreventiveSerializer(serializers.ModelSerializer):
    type_action_display = serializers.CharField(
        source='get_type_action_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not getattr(
                user, 'can_view_cout_non_qualite', True):
            fields.pop('cout', None)
        return fields

    class Meta:
        model = ActionCorrectivePreventive
        fields = [
            'id', 'non_conformite', 'type_action', 'type_action_display',
            'description', 'cause_racine', 'responsable', 'echeance',
            'statut', 'statut_display', 'efficace', 'commentaire_verification',
            'date_verification', 'verifiee_par',
            # XQHS22 — coût interne (gardé par permission).
            'cout',
            'date_creation',
        ]
        read_only_fields = [
            'efficace', 'commentaire_verification', 'date_verification',
            'verifiee_par', 'date_creation',
        ]

    def validate_non_conformite(self, value):
        return _meme_societe(self, value, 'Non-conformité')


class DerogationSerializer(serializers.ModelSerializer):
    """Acceptation en l'état bornée (dérogation) liée à une NCR (XQHS2).

    ``company`` posée côté serveur ; le ``statut`` bascule sur ``expiree``
    côté modèle (jamais lu du corps).
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    statut_courant = serializers.SerializerMethodField()

    class Meta:
        model = Derogation
        fields = [
            'id', 'non_conformite', 'justification', 'evaluation_risque',
            'quantite_max', 'date_debut', 'date_expiration',
            'prealerte_jours', 'approbateur', 'statut', 'statut_display',
            'statut_courant', 'date_creation',
        ]
        read_only_fields = ['statut', 'date_creation']

    def get_statut_courant(self, obj):
        return obj.statut_calcule()

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
            'valeur', 'conforme', 'photo_key', 'code_defaut',
            'date_releve', 'releve_par', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_plan_chantier(self, value):
        return _meme_societe(self, value, "Plan d'inspection chantier")

    def validate_point(self, value):
        return _meme_societe(self, value, 'Point de contrôle')

    def validate_code_defaut(self, value):
        return _meme_societe(self, value, 'Code de défaut')


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
    # WIR128 — délivreur / valideur écrits par id utilisateur (FK), affichés par
    # nom complet (libellé lisible sans jointure côté client).
    delivre_par_nom = serializers.SerializerMethodField()
    valide_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = PermisTravail
        fields = [
            'id', 'reference', 'titre', 'type_permis', 'type_permis_display',
            'statut', 'statut_display', 'chantier_id', 'date_debut',
            'date_fin', 'delivre_par', 'delivre_par_nom', 'valide_par',
            'valide_par_nom', 'mesures_prevention', 'notes', 'date_creation',
        ]
        read_only_fields = ['reference', 'statut', 'date_creation']

    @staticmethod
    def _user_nom(user):
        if user is None:
            return ''
        return user.get_full_name() or user.username

    def get_delivre_par_nom(self, obj):
        return self._user_nom(obj.delivre_par)

    def get_valide_par_nom(self, obj):
        return self._user_nom(obj.valide_par)

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
            'statut', 'statut_display', 'notes', 'frequence_mois',
            'contacts', 'secouristes',
            'nb_contacts', 'nb_secouristes', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class IncidentSerializer(serializers.ModelSerializer):
    """Registre des incidents HSE (QHSE29).

    ``company`` et ``declare_par`` sont posés côté serveur (jamais lus du corps) ;
    la ``reference`` est attribuée côté serveur (jamais lue du corps). Expose les
    libellés lisibles de ``type_incident``, ``gravite`` et ``statut``.

    XQHS19 — champs environnement (substance/quantité/milieu/notification)
    tous optionnels ; ``notification_en_retard`` est calculé (lecture seule).
    """
    type_incident_display = serializers.CharField(
        source='get_type_incident_display', read_only=True)
    gravite_display = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    milieu_touche_display = serializers.CharField(
        source='get_milieu_touche_display', read_only=True, default='')
    declare_par_nom = serializers.CharField(
        source='declare_par.username', read_only=True, default=None)
    notification_en_retard = serializers.BooleanField(read_only=True)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user is not None and not getattr(
                user, 'can_view_cout_non_qualite', True):
            fields.pop('cout', None)
        return fields

    class Meta:
        model = Incident
        fields = [
            'id', 'reference', 'titre', 'type_incident',
            'type_incident_display', 'gravite', 'gravite_display', 'statut',
            'statut_display', 'chantier_id', 'date_incident', 'description',
            'action_immediate', 'declare_par', 'declare_par_nom',
            'code_defaut', 'substance', 'quantite_estimee', 'quantite_unite',
            'milieu_touche', 'milieu_touche_display', 'notification_requise',
            'autorite_notifiee', 'date_notification',
            'date_limite_notification', 'notification_en_retard',
            # XQHS22 — coût interne (gardé par permission).
            'cout',
            'date_creation',
        ]
        read_only_fields = ['reference', 'declare_par', 'date_creation']

    def validate_code_defaut(self, value):
        return _meme_societe(self, value, 'Code de défaut')


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
            # XQHS1 — ITT + certificat/consolidation/conciliation + volet MP.
            'jours_itt', 'date_certificat_initial', 'date_consolidation',
            'conciliation_statut', 'est_maladie_professionnelle',
            'type_maladie_professionnelle', 'exposition_mp',
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


class EtapeDeclarationAtSerializer(serializers.ModelSerializer):
    """Étape légale datée de la chaîne AT/MP (loi 18-12, XQHS1).

    ``company`` posée côté serveur ; ``echeance``/``statut`` calculés côté
    serveur (jamais lus du corps). ``fait_le`` se pose via l'action
    ``marquer-fait`` du viewset plutôt qu'un PATCH direct, pour garder le
    recalcul de ``statut`` centralisé côté service.
    """
    type_etape_display = serializers.CharField(
        source='get_type_etape_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = EtapeDeclarationAt
        fields = [
            'id', 'declaration', 'type_etape', 'type_etape_display',
            'echeance', 'fait_le', 'statut', 'statut_display', 'notes',
            'date_creation',
        ]
        read_only_fields = ['echeance', 'statut', 'date_creation']

    def validate_declaration(self, value):
        return _meme_societe(self, value, 'Déclaration CNSS')


class InspectionSecuriteSerializer(serializers.ModelSerializer):
    """Inspection sécurité planifiée → NCR (QHSE33).

    ``company``/``inspecteur``/``reference``/``ncr`` sont posés côté serveur
    (jamais lus du corps). Le rattachement au chantier reste une référence lâche
    (``chantier_id``).
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    resultat_display = serializers.CharField(
        source='get_resultat_display', read_only=True)

    class Meta:
        model = InspectionSecurite
        fields = [
            'id', 'reference', 'titre', 'statut', 'statut_display',
            'resultat', 'resultat_display', 'chantier_id', 'date_prevue',
            'date_realisee', 'inspecteur', 'observations', 'ncr',
            'date_creation',
        ]
        read_only_fields = [
            'reference', 'inspecteur', 'ncr', 'date_creation',
        ]


class DechetSerializer(serializers.ModelSerializer):
    """Type de déchet du référentiel (QHSE36, loi 28-00).

    ``company`` posée côté serveur. ``dangereux`` (dérivé de la catégorie) est
    exposé en lecture seule.
    """
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    mode_traitement_display = serializers.CharField(
        source='get_mode_traitement_display', read_only=True)
    dangereux = serializers.BooleanField(read_only=True)

    class Meta:
        model = Dechet
        fields = [
            'id', 'libelle', 'code', 'categorie', 'categorie_display',
            'unite', 'mode_traitement', 'mode_traitement_display',
            'description', 'actif', 'dangereux', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class BordereauSuiviDechetSerializer(serializers.ModelSerializer):
    """Bordereau de suivi des déchets (BSD — QHSE36, loi 28-00).

    ``company`` / ``reference`` posées côté serveur. Le FK ``dechet`` est validé
    même-société. La règle « BSD réservé aux déchets DANGEREUX » (loi 28-00) est
    appliquée côté vue/service à la création. Le ``statut`` est piloté par
    actions détail, en lecture seule au CRUD.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    dechet_libelle = serializers.CharField(
        source='dechet.libelle', read_only=True)

    class Meta:
        model = BordereauSuiviDechet
        fields = [
            'id', 'reference', 'dechet', 'dechet_libelle', 'statut',
            'statut_display', 'chantier_id', 'quantite', 'producteur',
            'transporteur', 'eliminateur', 'date_emission',
            'date_enlevement', 'date_traitement', 'notes', 'date_creation',
        ]
        read_only_fields = ['reference', 'statut', 'date_creation']

    def validate_dechet(self, value):
        return _meme_societe(self, value, 'Déchet')


class RecyclageModuleSerializer(serializers.ModelSerializer):
    """Recyclage / fin de vie d'un lot de modules PV (QHSE37).

    ``company`` / ``reference`` posées côté serveur. Le FK ``bordereau`` (BSD
    QHSE36) est validé même-société. Le ``statut`` est piloté par actions détail,
    en lecture seule au CRUD.
    """
    motif_display = serializers.CharField(
        source='get_motif_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = RecyclageModule
        fields = [
            'id', 'reference', 'marque', 'modele', 'nombre_modules',
            'masse_kg', 'motif', 'motif_display', 'statut', 'statut_display',
            'filiere', 'chantier_id', 'bordereau', 'date_collecte',
            'date_recyclage', 'notes', 'date_creation',
        ]
        read_only_fields = ['reference', 'statut', 'date_creation']

    def validate_bordereau(self, value):
        return _meme_societe(self, value, 'Bordereau de suivi')


class ConformiteEnvironnementaleSerializer(serializers.ModelSerializer):
    """Conformité environnementale + échéance (QHSE38).

    ``company`` posée côté serveur. ``statut_courant`` recalcule l'état réel à la
    volée (expiré / à renouveler / statut enregistré). Le FK ``responsable`` est
    validé comme appartenant à la même société.
    """
    type_conformite_display = serializers.CharField(
        source='get_type_conformite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    statut_courant = serializers.SerializerMethodField()

    class Meta:
        model = ConformiteEnvironnementale
        fields = [
            'id', 'intitule', 'type_conformite', 'type_conformite_display',
            'statut', 'statut_display', 'statut_courant', 'autorite',
            'reference_dossier', 'chantier_id', 'date_obtention',
            'date_expiration', 'prealerte_jours', 'responsable', 'notes',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def get_statut_courant(self, obj):
        return obj.statut_calcule()

    def validate_responsable(self, value):
        request = self.context.get('request')
        if value is not None and request is not None:
            if value.company_id != request.user.company_id:
                raise serializers.ValidationError('Responsable inconnu.')
        return value


class LigneBilanCarboneSerializer(serializers.ModelSerializer):
    """Ligne d'émission d'un bilan carbone (QHSE39).

    ``company`` posée côté serveur. ``tco2e`` (quantité × facteur) exposé en
    lecture seule. Le FK ``bilan`` est validé même-société.
    """
    scope_display = serializers.CharField(
        source='get_scope_display', read_only=True)
    tco2e = serializers.DecimalField(
        max_digits=18, decimal_places=3, read_only=True)

    class Meta:
        model = LigneBilanCarbone
        fields = [
            'id', 'bilan', 'libelle', 'scope', 'scope_display', 'categorie',
            'quantite', 'unite', 'facteur_emission', 'tco2e', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_bilan(self, value):
        return _meme_societe(self, value, 'Bilan')


class BilanCarboneSerializer(serializers.ModelSerializer):
    """Bilan carbone interne (scopes 1/2/3 — QHSE39).

    ``company`` posée côté serveur. Les totaux par scope et le total global
    (``total_scope_1/2/3`` / ``total_tco2e``) sont DÉRIVÉS des lignes — exposés
    en lecture seule.
    """
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    total_scope_1 = serializers.DecimalField(
        max_digits=18, decimal_places=3, read_only=True)
    total_scope_2 = serializers.DecimalField(
        max_digits=18, decimal_places=3, read_only=True)
    total_scope_3 = serializers.DecimalField(
        max_digits=18, decimal_places=3, read_only=True)
    total_tco2e = serializers.DecimalField(
        max_digits=18, decimal_places=3, read_only=True)

    class Meta:
        model = BilanCarbone
        fields = [
            'id', 'libelle', 'annee', 'statut', 'statut_display',
            'perimetre', 'notes', 'total_scope_1', 'total_scope_2',
            'total_scope_3', 'total_tco2e', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class IndicateurESGSerializer(serializers.ModelSerializer):
    """Indicateur ESG (E/S/G) + export reporting (QHSE40).

    ``company`` posée côté serveur. ``atteinte_cible`` (dérivé valeur/cible selon
    la tendance souhaitée) exposé en lecture seule. Le FK ``bilan_carbone``
    (QHSE39) est validé même-société.
    """
    pilier_display = serializers.CharField(
        source='get_pilier_display', read_only=True)
    tendance_souhaitee_display = serializers.CharField(
        source='get_tendance_souhaitee_display', read_only=True)
    atteinte_cible = serializers.BooleanField(read_only=True, allow_null=True)

    class Meta:
        model = IndicateurESG
        fields = [
            'id', 'code', 'libelle', 'pilier', 'pilier_display', 'valeur',
            'cible', 'unite', 'annee', 'periode', 'tendance_souhaitee',
            'tendance_souhaitee_display', 'atteinte_cible', 'bilan_carbone',
            'notes', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_bilan_carbone(self, value):
        return _meme_societe(self, value, 'Bilan carbone')


# ── XQHS3 — Contrôle qualité à la réception fournisseur ─────────────────────

class PointControleReceptionSerializer(serializers.ModelSerializer):
    type_releve_display = serializers.CharField(
        source='get_type_releve_display', read_only=True)

    class Meta:
        model = PointControleReception
        fields = [
            'id', 'plan', 'ordre', 'intitule', 'type_releve',
            'type_releve_display', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_plan(self, value):
        return _meme_societe(self, value, 'Plan de contrôle réception')


class PlanControleReceptionSerializer(serializers.ModelSerializer):
    """Plan de contrôle qualité à la réception fournisseur (XQHS3).

    ``company`` posée côté serveur. Les FK ``produit``/``categorie`` pointent
    vers ``stock`` (FK-chaîne) : validés même-société par le sérialiseur.
    """
    points = PointControleReceptionSerializer(many=True, read_only=True)

    class Meta:
        model = PlanControleReception
        fields = [
            'id', 'nom', 'produit', 'categorie', 'taux_echantillonnage',
            'actif', 'points', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_produit(self, value):
        return _meme_societe(self, value, 'Produit')

    def validate_categorie(self, value):
        return _meme_societe(self, value, 'Catégorie')


class ControleReceptionSerializer(serializers.ModelSerializer):
    """Exécution d'un contrôle qualité à la réception fournisseur (XQHS3).

    ``company``/``controleur``/``date_controle`` posés côté serveur. Le
    ``verdict`` se pose via l'action ``statuer`` du viewset (jamais un PATCH
    direct), pour garder centralisée la levée automatique de NCR sur refus.
    """
    verdict_display = serializers.CharField(
        source='get_verdict_display', read_only=True)
    plan_nom = serializers.CharField(source='plan.nom', read_only=True)

    class Meta:
        model = ControleReception
        fields = [
            'id', 'plan', 'plan_nom', 'reception_id', 'produit_id', 'verdict',
            'verdict_display', 'controleur', 'notes', 'non_conformite',
            'date_controle', 'date_creation',
        ]
        read_only_fields = [
            'verdict', 'controleur', 'non_conformite', 'date_controle',
            'date_creation',
        ]

    def validate_plan(self, value):
        return _meme_societe(self, value, 'Plan de contrôle réception')


class LienSignalementPublicSerializer(serializers.ModelSerializer):
    """Lien public tokenisé (QR) par chantier (XQHS16). ``token`` en lecture
    seule (posé côté serveur, jamais choisi par le client)."""

    class Meta:
        model = LienSignalementPublic
        fields = [
            'id', 'chantier_id', 'token', 'libelle', 'actif',
            'responsable_hse', 'created_by', 'date_creation',
        ]
        read_only_fields = ['token', 'created_by', 'date_creation']

    def validate_responsable_hse(self, value):
        return _meme_societe(self, value, 'Responsable HSE')


class SignalementPublicSerializer(serializers.ModelSerializer):
    """Signalement reçu via un lien public tokenisé (XQHS16). Lecture interne
    (liste/détail côté ERP) — la CRÉATION publique passe par la vue dédiée
    ``public_signalement`` (jamais par ce viewset authentifié)."""
    anonyme = serializers.BooleanField(read_only=True)
    type_signalement_display = serializers.CharField(
        source='get_type_signalement_display', read_only=True)

    class Meta:
        model = SignalementPublic
        fields = [
            'id', 'lien', 'type_signalement', 'type_signalement_display',
            'description', 'photo_url', 'nom', 'telephone', 'source',
            'anonyme', 'incident', 'date_creation',
        ]
        read_only_fields = ['source', 'date_creation']


class ObservationSecuriteSerializer(serializers.ModelSerializer):
    """Observation sécurité comportementale (BBS, XQHS17). ``company`` et
    ``observateur`` posés côté serveur (jamais lus du corps de requête)."""
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)
    type_observation_display = serializers.CharField(
        source='get_type_observation_display', read_only=True)

    class Meta:
        model = ObservationSecurite
        fields = [
            'id', 'date_observation', 'chantier_id', 'categorie',
            'categorie_display', 'type_observation',
            'type_observation_display', 'description', 'feedback_donne',
            'observateur', 'action_liee', 'non_conformite_liee',
            'date_creation',
        ]
        read_only_fields = [
            'observateur', 'action_liee', 'non_conformite_liee',
            'date_creation',
        ]


class ExerciceUrgenceSerializer(serializers.ModelSerializer):
    """Exercice d'urgence rattaché à un plan (XQHS18). ``company`` posée côté
    serveur. La réalisation (chrono/observations) se pose via l'action
    ``realiser`` du viewset (jamais un PATCH direct des champs de résultat)."""
    type_exercice_display = serializers.CharField(
        source='get_type_exercice_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    plan_titre = serializers.CharField(source='plan.titre', read_only=True)

    class Meta:
        model = ExerciceUrgence
        fields = [
            'id', 'plan', 'plan_titre', 'type_exercice',
            'type_exercice_display', 'date_prevue', 'date_realisee',
            'duree_evacuation_secondes', 'nb_participants',
            'participants_libre', 'observations', 'statut', 'statut_display',
            'capa_liee', 'date_creation',
        ]
        read_only_fields = [
            'date_realisee', 'duree_evacuation_secondes', 'nb_participants',
            'participants_libre', 'observations', 'statut', 'capa_liee',
            'date_creation',
        ]

    def validate_plan(self, value):
        return _meme_societe(self, value, "Plan d'urgence")


class AspectEnvironnementalSerializer(serializers.ModelSerializer):
    """Aspect & impact environnemental coté (XQHS20, ISO 14001 6.1.2).

    ``criticite``/``significatif`` sont dérivés (lecture seule) : jamais
    stockés, toujours recalculés depuis fréquence × gravité vs seuil."""
    criticite = serializers.IntegerField(read_only=True)
    significatif = serializers.BooleanField(read_only=True)
    condition_display = serializers.CharField(
        source='get_condition_display', read_only=True)

    class Meta:
        model = AspectEnvironnemental
        fields = [
            'id', 'activite', 'aspect', 'impact', 'condition',
            'condition_display', 'frequence', 'gravite',
            'seuil_significativite', 'criticite', 'significatif',
            'controles_existants', 'procedure', 'objectif', 'date_revue',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_procedure(self, value):
        return _meme_societe(self, value, 'Procédure qualité')

    def validate_objectif(self, value):
        return _meme_societe(self, value, 'Objectif QHSE')


class ReleveConsommationSerializer(serializers.ModelSerializer):
    """Relevé périodique de consommation par site (XQHS21). ``company`` posée
    côté serveur."""
    type_energie_display = serializers.CharField(
        source='get_type_energie_display', read_only=True)
    source_display = serializers.CharField(
        source='get_source_display', read_only=True)

    class Meta:
        model = ReleveConsommation
        fields = [
            'id', 'site_libelle', 'type_energie', 'type_energie_display',
            'periode', 'quantite', 'source', 'source_display',
            'piece_jointe_url', 'date_creation',
        ]
        read_only_fields = ['date_creation']


class DemandeChangementSerializer(serializers.ModelSerializer):
    """Demande de gestion du changement (MOC, XQHS24). ``company`` posée côté
    serveur. Le ``statut`` avance via l'action ``transitionner`` du viewset
    (jamais un PATCH direct) pour garder le gate d'approbation centralisé."""
    type_changement_display = serializers.CharField(
        source='get_type_changement_display', read_only=True)
    classification_impact_display = serializers.CharField(
        source='get_classification_impact_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    nb_capa_liees = serializers.IntegerField(
        source='capa_liees.count', read_only=True)

    class Meta:
        model = DemandeChangement
        fields = [
            'id', 'type_changement', 'type_changement_display', 'description',
            'justification', 'classification_impact',
            'classification_impact_display', 'revue_risques',
            'evaluation_risque', 'documents_formations_impactes',
            'approbateur', 'date_approbation', 'checklist_verification',
            'statut', 'statut_display', 'est_temporaire', 'date_expiration',
            'nb_capa_liees', 'date_creation',
        ]
        read_only_fields = [
            'approbateur', 'date_approbation', 'statut', 'date_creation',
        ]

    def validate_evaluation_risque(self, value):
        return _meme_societe(self, value, 'Évaluation des risques')


class RevueVeilleReglementaireSerializer(serializers.ModelSerializer):
    """Revue (occurrence) d'une veille réglementaire (XQHS26). ``company``
    posée côté serveur ; la ``conclusion`` n'avance QUE via l'action
    ``conclure`` du viewset (jamais un PATCH direct — sinon le registre légal
    XQHS8 et la prochaine échéance ne seraient pas mis à jour)."""
    conclusion_display = serializers.CharField(
        source='get_conclusion_display', read_only=True)
    veille_texte = serializers.CharField(
        source='veille.texte_suivi', read_only=True)

    class Meta:
        model = RevueVeilleReglementaire
        fields = [
            'id', 'veille', 'veille_texte', 'date_echeance', 'date_revue',
            'conclusion', 'conclusion_display', 'impact_evalue',
            'resume_ia', 'date_creation',
        ]
        read_only_fields = [
            'date_revue', 'conclusion', 'impact_evalue', 'resume_ia',
            'date_creation',
        ]

    def validate_veille(self, value):
        return _meme_societe(self, value, 'Veille réglementaire')


class VeilleReglementaireSerializer(serializers.ModelSerializer):
    """Texte réglementaire suivi + cadence de revue (XQHS26). ``company``
    posée côté serveur. ``date_derniere_revue``/``date_prochaine_revue``/
    ``registre_conformite`` sont en lecture seule : ils n'avancent que via
    les revues (``qhse.services.conclure_revue_veille``), jamais un PATCH
    direct."""
    revues = RevueVeilleReglementaireSerializer(many=True, read_only=True)

    class Meta:
        model = VeilleReglementaire
        fields = [
            'id', 'texte_suivi', 'source', 'description', 'cadence_jours',
            'date_derniere_revue', 'date_prochaine_revue', 'responsable',
            'registre_conformite', 'revues', 'date_creation',
        ]
        read_only_fields = [
            'date_derniere_revue', 'date_prochaine_revue',
            'registre_conformite', 'date_creation',
        ]

    def validate_responsable(self, value):
        return _meme_societe(self, value, 'Responsable')


# ── WIR115 — Check-in sécurité (technicien seul sur site) ────────────────────
class CheckinSecuriteSerializer(serializers.ModelSerializer):
    """Cycle check-in/check-out d'un technicien seul sur site à risque.

    ``company`` posée côté serveur ; ``technicien`` par défaut = utilisateur
    courant (posé au ``perform_create`` de la vue) mais surchargeable par un
    membre de la même société. ``escalade_declenchee``/``escalade_le`` ne sont
    pilotés que par la tâche d'escalade (lecture seule au CRUD)."""
    technicien_nom = serializers.SerializerMethodField()
    en_retard = serializers.SerializerMethodField()

    class Meta:
        model = CheckinSecurite
        fields = [
            'id', 'technicien', 'technicien_nom', 'intervention_id',
            'site_ref', 'heure_checkin', 'heure_checkout_prevue',
            'heure_checkout_reelle', 'delai_escalade_min',
            'escalade_declenchee', 'escalade_le', 'en_retard', 'date_creation',
        ]
        read_only_fields = [
            'escalade_declenchee', 'escalade_le', 'date_creation',
        ]
        extra_kwargs = {'technicien': {'required': False}}

    @staticmethod
    def _nom(user):
        return (user.get_full_name() or user.username) if user else ''

    def get_technicien_nom(self, obj):
        return self._nom(obj.technicien)

    def get_en_retard(self, obj):
        return obj.en_retard()

    def validate_technicien(self, value):
        return _meme_societe(self, value, 'Technicien')


# ── WIR115 — SCAR : demande d'action corrective fournisseur ──────────────────
class DemandeActionFournisseurSerializer(serializers.ModelSerializer):
    """SCAR — demande d'action corrective adressée à un fournisseur.

    ``company`` posée côté serveur. Le ``statut`` et les champs de réponse /
    vérification sont en lecture seule au CRUD : ils n'avancent que par les
    actions ``repondre`` / ``verifier`` de la vue (jamais un PATCH direct)."""
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = DemandeActionFournisseur
        fields = [
            'id', 'fournisseur', 'fournisseur_nom', 'ncr_source',
            'description_defaut', 'echeance_reponse',
            'cause_racine_fournisseur', 'action_fournisseur',
            'preuve_attachment_ids', 'statut', 'statut_display',
            'date_reponse', 'efficace', 'date_verification', 'verifiee_par',
            'date_creation',
        ]
        read_only_fields = [
            'statut', 'cause_racine_fournisseur', 'action_fournisseur',
            'date_reponse', 'efficace', 'date_verification', 'verifiee_par',
            'date_creation',
        ]

    def validate_fournisseur(self, value):
        return _meme_societe(self, value, 'Fournisseur')

    def validate_ncr_source(self, value):
        return _meme_societe(self, value, 'NCR source')
