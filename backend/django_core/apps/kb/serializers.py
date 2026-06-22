"""Sérialiseurs de la Base de connaissances.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``auteur`` est posé côté serveur.
"""
from rest_framework import serializers

from .models import KbArticle, KbArticleLien, KbArticleVersion


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


class KbArticleVersionSerializer(serializers.ModelSerializer):
    """Lecture seule : les versions sont des instantanés posés côté serveur."""
    auteur_nom = serializers.CharField(
        source='auteur.get_full_name', read_only=True)

    class Meta:
        model = KbArticleVersion
        fields = [
            'id', 'article', 'version', 'titre', 'contenu', 'auteur',
            'auteur_nom', 'date_creation',
        ]
        read_only_fields = fields


class KbArticleLienSerializer(serializers.ModelSerializer):
    """Lien article → objet métier d'une autre app (référence lâche typée).

    ``company`` n'est jamais exposée : elle est posée côté serveur. L'``article``
    reçu est validé comme appartenant à la société de l'utilisateur.
    """
    type_cible_display = serializers.CharField(
        source='get_type_cible_display', read_only=True)

    class Meta:
        model = KbArticleLien
        fields = [
            'id', 'article', 'type_cible', 'type_cible_display', 'cible_id',
            'libelle', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_article(self, article):
        """L'article rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and article.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Cet article n'appartient pas à votre société.")
        return article
