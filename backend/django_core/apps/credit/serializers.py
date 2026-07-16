"""apps.credit.serializers — peuplé tâche par tâche."""
from rest_framework import serializers

from .models import LimiteCredit


class LimiteCreditSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimiteCredit
        fields = [
            'id', 'client', 'montant_limite', 'devise', 'mode_hold',
            'actif', 'motif_null', 'cree_par', 'date_creation',
            'date_modification',
        ]
        read_only_fields = ['id', 'cree_par', 'date_creation', 'date_modification']
