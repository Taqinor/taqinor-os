"""FG268-FG271 — sérialiseurs du dossier réglementaire (côté ventes).

``company`` et ``created_by`` sont TOUJOURS forcés côté serveur dans les
viewsets, jamais désérialisés. Aucun prix exposé.
"""
from rest_framework import serializers

from .models import (
    RegulatoryDossier, DossierChecklistItem, DossierExchange,
    SubventionDossier, Regularisation8221,
)


class DossierChecklistItemSerializer(serializers.ModelSerializer):
    """FG268 — pièce/étape de checklist d'un dossier."""

    class Meta:
        model = DossierChecklistItem
        fields = [
            'id', 'dossier', 'code', 'libelle', 'etape', 'statut',
            'obligatoire', 'date_echeance', 'relance_due', 'ordre',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class RegulatoryDossierSerializer(serializers.ModelSerializer):
    """FG268 — dossier réglementaire de raccordement."""
    checklist_items = DossierChecklistItemSerializer(
        many=True, read_only=True)
    regime_label = serializers.CharField(
        source='get_regime_8221_display', read_only=True)
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = RegulatoryDossier
        fields = [
            'id', 'devis', 'chantier', 'regime_8221', 'regime_label',
            'statut', 'statut_label', 'operateur', 'reference_dossier',
            'date_depot', 'date_decision', 'notes',
            'checklist_items', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'regime_label', 'statut_label', 'checklist_items',
            'created_at', 'updated_at',
        ]


class DossierExchangeSerializer(serializers.ModelSerializer):
    """FG269 — échange de la navette opérateur."""
    sens_label = serializers.CharField(
        source='get_sens_display', read_only=True)
    type_label = serializers.CharField(
        source='get_type_echange_display', read_only=True)

    class Meta:
        model = DossierExchange
        fields = [
            'id', 'dossier', 'sens', 'sens_label', 'type_echange',
            'type_label', 'date_echange', 'objet', 'detail',
            'piece_jointe', 'created_at',
        ]
        read_only_fields = [
            'id', 'sens_label', 'type_label', 'created_at',
        ]


class SubventionDossierSerializer(serializers.ModelSerializer):
    """FG270 — dossier de subvention/incitation."""
    programme_label = serializers.CharField(
        source='get_programme_display', read_only=True)
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = SubventionDossier
        fields = [
            'id', 'devis', 'programme', 'programme_label', 'statut',
            'statut_label', 'montant_demande', 'montant_accorde',
            'reference', 'eligibilite_note', 'pieces',
            'date_depot', 'date_decision', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'programme_label', 'statut_label',
            'created_at', 'updated_at',
        ]


class Regularisation8221Serializer(serializers.ModelSerializer):
    """FG271 — régularisation Article 33 (installation existante)."""
    regime_label = serializers.CharField(
        source='get_regime_8221_display', read_only=True)
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Regularisation8221
        fields = [
            'id', 'devis', 'chantier', 'regime_8221', 'regime_label',
            'statut', 'statut_label', 'puissance_kwc',
            'date_mise_en_service_initiale', 'declaration_pdf', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'regime_label', 'statut_label',
            'created_at', 'updated_at',
        ]
