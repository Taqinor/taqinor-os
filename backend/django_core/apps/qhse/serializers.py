"""Sérialiseurs QHSE.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import (
    ActionCorrectivePreventive, NonConformite, PlanInspectionChantier,
    PlanInspectionModele, PointControleModele, ReleveControle,
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
            'chantier_id', 'signale_par', 'date_detection', 'date_creation',
        ]
        read_only_fields = ['signale_par', 'date_creation']


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
            'statut', 'statut_display', 'date_creation',
        ]
        read_only_fields = ['date_creation']

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

    class Meta:
        model = PlanInspectionChantier
        fields = [
            'id', 'modele', 'modele_nom', 'chantier_id', 'date_ouverture',
            'statut', 'statut_display', 'nb_releves', 'date_creation',
        ]
        read_only_fields = ['date_creation']

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
