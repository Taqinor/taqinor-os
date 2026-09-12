"""Sérialiseurs du module GRC & Conformité (NTGRC).

Règle commune : ``company`` n'est JAMAIS lue du corps de la requête — elle est
imposée côté serveur par ``CompanyScopedModelViewSet``.
"""
from rest_framework import serializers

from .models import JournalDestruction, PolitiqueRetentionObjet


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
