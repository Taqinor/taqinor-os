"""Sérialiseurs de la Gestion des contrats.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). ``created_by`` est également posé côté
serveur.
"""
from rest_framework import serializers

from .models import Contrat, ContratLien, PartieContrat


class ContratSerializer(serializers.ModelSerializer):
    type_contrat_display = serializers.CharField(
        source='get_type_contrat_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Contrat
        fields = [
            'id', 'reference', 'type_contrat', 'type_contrat_display',
            'objet', 'statut', 'statut_display', 'client_id', 'date_debut',
            'date_fin', 'montant', 'devise', 'created_by', 'date_creation',
        ]
        read_only_fields = ['created_by', 'date_creation']


class PartieContratSerializer(serializers.ModelSerializer):
    type_partie_display = serializers.CharField(
        source='get_type_partie_display', read_only=True)

    class Meta:
        model = PartieContrat
        fields = [
            'id', 'contrat', 'type_partie', 'type_partie_display', 'nom',
            'fonction', 'email', 'telephone', 'ordre',
        ]

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur.

        Empêche d'attacher une partie à un contrat d'une autre société (la
        société de la partie elle-même est posée côté serveur par le
        ``TenantMixin``).
        """
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat


class ContratLienSerializer(serializers.ModelSerializer):
    """Lien contrat → document métier d'une autre app (référence lâche typée).

    ``company`` n'est jamais exposée : elle est posée côté serveur. Le
    ``contrat`` reçu est validé comme appartenant à la société de l'utilisateur.
    """
    type_cible_display = serializers.CharField(
        source='get_type_cible_display', read_only=True)

    class Meta:
        model = ContratLien
        fields = [
            'id', 'contrat', 'type_cible', 'type_cible_display', 'cible_id',
            'libelle', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_contrat(self, contrat):
        """Le contrat rattaché doit appartenir à la société de l'utilisateur."""
        request = self.context.get('request')
        if request is not None and contrat.company_id != request.user.company_id:
            raise serializers.ValidationError(
                "Ce contrat n'appartient pas à votre société.")
        return contrat
