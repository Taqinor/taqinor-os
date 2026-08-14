"""Serializers du module « conversation_ai » (Groupe NTAI)."""
from rest_framework import serializers

from .models import AppelCommercial


class AppelCommercialSerializer(serializers.ModelSerializer):
    """Enregistrement d'appel — le fichier est reçu en écriture SEULEMENT.

    ``company`` n'est JAMAIS acceptée du corps de la requête : le viewset la
    force côté serveur. ``fichier_key``/``transcript``/``statut`` sont produits
    par le serveur (téléversement + tâche de transcription).
    """

    fichier = serializers.FileField(write_only=True, required=False)

    class Meta:
        model = AppelCommercial
        fields = [
            'id', 'lead', 'client', 'fichier', 'fichier_key', 'mime',
            'duree_s', 'transcript', 'statut', 'message', 'transcrit_le',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'fichier_key', 'mime', 'transcript', 'statut', 'message',
            'transcrit_le', 'created_at', 'updated_at',
        ]

    def _company(self):
        request = self.context.get('request')
        return getattr(getattr(request, 'user', None), 'company_id', None)

    def _meme_societe(self, value, libelle):
        """Refuse un rattachement appartenant à une AUTRE société.

        Sans cette garde, l'``id`` d'un lead d'une autre société passerait le
        ``PrimaryKeyRelatedField`` par défaut (dont le queryset n'est pas
        scopé) et rattacherait l'appel à travers les tenants.
        """
        company_id = self._company()
        if value is not None and company_id is not None:
            if getattr(value, 'company_id', None) != company_id:
                raise serializers.ValidationError(
                    f'{libelle} introuvable pour cette société.')
        return value

    def validate_lead(self, value):
        return self._meme_societe(value, 'Lead')

    def validate_client(self, value):
        return self._meme_societe(value, 'Client')
