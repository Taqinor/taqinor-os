"""Sérialiseurs du vertical BTP/EPC (Groupe NTCON)."""
from rest_framework import serializers

from .models import ReserveChantier, ReserveChantierHistorique, SignatureBtp


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur (cross-
    tenant refusé — pattern ``gestion_projet.serializers._meme_societe``)."""
    request = serializer.context.get('request')
    if value is not None and request is not None and request.user.company_id:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


def _valider_localisation_plan(value):
    """Valide la forme du pin plan : ``document_ged_id`` + x/y ∈ [0, 1]."""
    if not isinstance(value, dict):
        raise serializers.ValidationError(
            'localisation_plan doit être un objet JSON.')
    doc_id = value.get('document_ged_id')
    if not doc_id or not isinstance(doc_id, int):
        raise serializers.ValidationError(
            "localisation_plan.document_ged_id est requis (id du document GED).")
    for axe in ('x', 'y'):
        coord = value.get(axe)
        if coord is None or not isinstance(coord, (int, float)):
            raise serializers.ValidationError(
                f'localisation_plan.{axe} est requis (coordonnée normalisée 0-1).')
        if not (0 <= coord <= 1):
            raise serializers.ValidationError(
                f'localisation_plan.{axe} doit être compris entre 0 et 1.')
    return value


class ReserveChantierHistoriqueSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default='')

    class Meta:
        model = ReserveChantierHistorique
        fields = [
            'id', 'ancien_statut', 'nouveau_statut', 'motif',
            'auteur', 'auteur_nom', 'date_creation',
        ]
        read_only_fields = fields


class SignatureBtpSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignatureBtp
        fields = [
            'id', 'contexte', 'signataire_nom', 'signataire', 'methode',
            'date_signature', 'ip_adresse', 'user_agent',
        ]
        read_only_fields = fields


class ReserveChantierSerializer(serializers.ModelSerializer):
    historique = ReserveChantierHistoriqueSerializer(many=True, read_only=True)

    class Meta:
        model = ReserveChantier
        fields = [
            'id', 'chantier', 'lot', 'localisation_plan', 'description',
            'gravite', 'statut', 'responsable_leve', 'date_limite',
            'created_by', 'created_at', 'updated_at',
            'date_levee', 'leve_par', 'motif_contestation', 'historique',
        ]
        read_only_fields = [
            'id', 'statut', 'created_by', 'created_at', 'updated_at',
            'date_levee', 'leve_par', 'motif_contestation', 'historique',
        ]

    def validate_localisation_plan(self, value):
        return _valider_localisation_plan(value)

    def validate_chantier(self, value):
        return _meme_societe(self, value, 'Chantier')

    def validate_responsable_leve(self, value):
        return _meme_societe(self, value, 'Responsable')
