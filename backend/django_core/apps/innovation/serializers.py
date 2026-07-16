"""Sérialiseurs du module Innovation.

``company`` n'est jamais exposée en écriture : elle est posée côté serveur
(``CompanyScopedModelViewSet.perform_create``/``perform_update``).
``auteur``/``votant``/``created_by`` sont posés côté serveur.
"""
from rest_framework import serializers

from .models import VoteIdee


class VoteIdeeSerializer(serializers.ModelSerializer):
    votant_nom = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = VoteIdee
        fields = ['id', 'idee', 'votant', 'votant_nom', 'date']
        read_only_fields = ['votant', 'date']

    def get_votant_nom(self, obj):
        return getattr(obj.votant, 'username', None)
