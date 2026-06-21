"""Sérialiseurs de la Gestion documentaire (GED).

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
le ``TenantMixin`` (``perform_create``). Tous les FK reçus sont validés comme
appartenant à la société de l'utilisateur.
"""
from rest_framework import serializers

from .models import Document, DocumentVersion, Dossier


def _meme_societe(serializer, value, label):
    """Garde-fou : un FK doit appartenir à la société de l'utilisateur."""
    request = serializer.context.get('request')
    if value is not None and request is not None:
        if value.company_id != request.user.company_id:
            raise serializers.ValidationError(f'{label} inconnu.')
    return value


class DossierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dossier
        fields = ['id', 'nom', 'parent', 'chemin', 'date_creation']
        read_only_fields = ['chemin', 'date_creation']

    def validate_parent(self, value):
        return _meme_societe(self, value, 'Dossier parent')


class DocumentSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'dossier', 'titre', 'description', 'statut', 'statut_display',
            'created_by', 'date_creation',
        ]
        read_only_fields = ['created_by', 'date_creation']

    def validate_dossier(self, value):
        return _meme_societe(self, value, 'Dossier')


class DocumentVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentVersion
        fields = [
            'id', 'document', 'numero_version', 'file_key', 'filename', 'mime',
            'taille', 'checksum', 'date_creation',
        ]
        read_only_fields = ['date_creation']

    def validate_document(self, value):
        return _meme_societe(self, value, 'Document')
