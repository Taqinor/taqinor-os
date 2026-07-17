"""apps.credit.serializers — peuplé tâche par tâche."""
from rest_framework import serializers

from .models import (
    ConditionPaiementSegment, DerogationCredit, LimiteCredit, ReglageCredit,
    SegmentClientCredit,
)


class LimiteCreditSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimiteCredit
        fields = [
            'id', 'client', 'montant_limite', 'devise', 'mode_hold',
            'actif', 'motif_null', 'cree_par', 'date_creation',
            'date_modification',
        ]
        read_only_fields = ['id', 'cree_par', 'date_creation', 'date_modification']


class ReglageCreditSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReglageCredit
        fields = [
            'id', 'mode_hold_defaut', 'inclure_bc_non_factures',
            'inclure_devis_en_cours', 'seuil_alerte_pct',
            'date_creation', 'date_modification',
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification']


class ConditionPaiementSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConditionPaiementSegment
        fields = [
            'id', 'segment', 'delai_paiement_jours', 'pct_acompte_defaut',
            'mode_hold_override', 'date_creation', 'date_modification',
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification']


class SegmentClientCreditSerializer(serializers.ModelSerializer):
    class Meta:
        model = SegmentClientCredit
        fields = ['id', 'client', 'segment', 'date_modification']
        read_only_fields = ['id', 'date_modification']


class DerogationCreditSerializer(serializers.ModelSerializer):
    est_valide = serializers.BooleanField(read_only=True)

    class Meta:
        model = DerogationCredit
        fields = [
            'id', 'client', 'devis', 'montant_demande', 'motif', 'statut',
            'demandeur', 'approuvee_par', 'date_decision', 'valide_jusqu_au',
            'date_creation', 'est_valide',
        ]
        read_only_fields = [
            'id', 'statut', 'demandeur', 'approuvee_par', 'date_decision',
            'valide_jusqu_au', 'date_creation', 'est_valide',
        ]
