"""Sérialiseurs de la Gestion de projet.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import Projet, ProjetActivity, ProjetChantier, ProjetLien


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class ProjetSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Projet
        fields = [
            'id', 'code', 'nom', 'description', 'statut', 'statut_display',
            'client_id', 'date_debut', 'date_fin_prevue', 'responsable',
            'budget_total', 'date_creation',
        ]
        # ``statut`` est piloté UNIQUEMENT par les actions de transition
        # (machine à états côté serveur) — jamais écrit depuis le corps de
        # requête (création ou PATCH).
        read_only_fields = ['statut', 'date_creation']

    def validate_responsable(self, value):
        return _meme_societe(self, value, 'Responsable')


class ProjetActivitySerializer(serializers.ModelSerializer):
    """Entrée du journal des transitions de statut d'un projet (lecture seule).

    ``company`` et ``auteur`` sont posés côté serveur ; jamais exposés en
    écriture.
    """
    auteur_nom = serializers.CharField(
        source='auteur.username', read_only=True, default='')

    class Meta:
        model = ProjetActivity
        fields = [
            'id', 'projet', 'old_value', 'new_value', 'auteur', 'auteur_nom',
            'date_creation',
        ]
        read_only_fields = fields


class ProjetChantierSerializer(serializers.ModelSerializer):
    projet_code = serializers.CharField(source='projet.code', read_only=True)

    class Meta:
        model = ProjetChantier
        fields = [
            'id', 'projet', 'projet_code', 'chantier_id', 'libelle',
            'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')


class ProjetLienSerializer(serializers.ModelSerializer):
    """Lien projet → document métier d'une autre app (référence lâche typée).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le ``projet``
    reçu est validé comme appartenant à la société de l'utilisateur.
    """
    projet_code = serializers.CharField(source='projet.code', read_only=True)
    type_cible_display = serializers.CharField(
        source='get_type_cible_display', read_only=True)

    class Meta:
        model = ProjetLien
        fields = [
            'id', 'projet', 'projet_code', 'type_cible', 'type_cible_display',
            'cible_id', 'libelle', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_projet(self, value):
        return _meme_societe(self, value, 'Projet')
