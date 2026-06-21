"""Sérialiseurs de la Base de connaissances.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``auteur`` est posé côté serveur.
"""
from rest_framework import serializers

from .models import KbArticle


class KbArticleSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    auteur_nom = serializers.CharField(
        source='auteur.get_full_name', read_only=True)

    class Meta:
        model = KbArticle
        fields = [
            'id', 'titre', 'corps', 'categorie', 'tags', 'statut',
            'statut_display', 'auteur', 'auteur_nom', 'date_creation',
            'date_modification',
        ]
        read_only_fields = [
            'auteur', 'date_creation', 'date_modification']
