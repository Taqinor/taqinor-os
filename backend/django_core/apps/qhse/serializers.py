"""Sérialiseurs QHSE.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import (
    ActionCorrectivePreventive, CritereAudit, GrilleAudit, NonConformite,
    PlanInspectionChantier, PlanInspectionModele, PointControleModele,
    QhseChatterEntry, ReleveControle, ReleveCourbeIV,
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
