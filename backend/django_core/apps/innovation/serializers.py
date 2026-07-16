"""Sérialiseurs du module Innovation.

``company`` n'est jamais exposée en écriture : elle est posée côté serveur
(``CompanyScopedModelViewSet.perform_create``/``perform_update``).
``auteur``/``votant``/``created_by`` sont posés côté serveur.
"""
from rest_framework import serializers

from .models import Idee, VoteIdee


class IdeeSerializer(serializers.ModelSerializer):
    """Sérialiseur de liste/écriture (NTIDE4) — auteur, votes, contexte."""

    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    auteur_nom = serializers.SerializerMethodField()
    linked_type_display = serializers.CharField(
        source='get_linked_type_display', read_only=True)
    # Exposé sous le nom du domaine (spec NTIDE1) — la colonne DB réelle
    # reste ``created_at`` (héritée de ``core.models.TenantModel``, ARC1).
    date_creation = serializers.DateTimeField(
        source='created_at', read_only=True)

    class Meta:
        model = Idee
        fields = [
            'id', 'titre', 'description', 'contexte', 'statut',
            'statut_display', 'auteur', 'auteur_nom', 'votes_count',
            'linked_type', 'linked_type_display', 'linked_id',
            'date_creation',
        ]
        # ``statut`` ne se modifie pas par PATCH direct : le cycle de vie
        # passe par les actions de transition (examiner/retenir/réaliser/
        # fermer, NTIDE5) qui appliquent la machine à états et journalisent
        # le chatter. ``votes_count`` est dénormalisé, maintenu par
        # VoteIdeeViewSet — jamais écrit directement.
        read_only_fields = ['auteur', 'votes_count', 'statut', 'date_creation']

    def get_auteur_nom(self, obj):
        return getattr(obj.auteur, 'username', None)


class VoteIdeeSerializer(serializers.ModelSerializer):
    votant_nom = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = VoteIdee
        fields = ['id', 'idee', 'votant', 'votant_nom', 'date']
        read_only_fields = ['votant', 'date']

    def get_votant_nom(self, obj):
        return getattr(obj.votant, 'username', None)
