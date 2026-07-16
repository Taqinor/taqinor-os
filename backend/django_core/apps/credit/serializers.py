"""apps.credit.serializers — peuplé tâche par tâche."""
from rest_framework import serializers

from .models import LimiteCredit, ReglageCredit


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
