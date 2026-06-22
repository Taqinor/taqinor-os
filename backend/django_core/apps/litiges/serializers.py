"""Sérialiseurs des Réclamations & litiges.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``created_by`` est posé côté serveur.
"""
from rest_framework import serializers

from .models import Reclamation, ReclamationActivity


class ReclamationActivitySerializer(serializers.ModelSerializer):
    """Entrée du chatter (changement de statut automatique ou note manuelle).

    Tous les champs sont en lecture seule côté API : les entrées sont créées
    exclusivement côté serveur (transitions de statut, action ``noter``).
    """
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = ReclamationActivity
        fields = [
            'id', 'reclamation', 'type', 'type_display', 'old_value',
            'new_value', 'message', 'auteur', 'auteur_nom', 'date_creation',
        ]
        read_only_fields = fields

    def get_auteur_nom(self, obj):
        return getattr(obj.auteur, 'username', None)


class ReclamationSerializer(serializers.ModelSerializer):
    type_reclamation_display = serializers.CharField(
        source='get_type_reclamation_display', read_only=True)
    gravite_display = serializers.CharField(
        source='get_gravite_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Reclamation
        fields = [
            'id', 'reference', 'type_reclamation', 'type_reclamation_display',
            'gravite', 'gravite_display', 'objet', 'description',
            'source_type', 'source_id', 'montant_conteste', 'statut',
            'statut_display', 'created_by', 'date_creation',
        ]
        # ``statut`` ne se modifie pas par PATCH direct : le cycle de vie passe
        # par les actions de transition (prendre_en_charge/resoudre/rejeter)
        # qui appliquent la machine à états et journalisent le chatter.
        read_only_fields = ['created_by', 'date_creation', 'statut']
