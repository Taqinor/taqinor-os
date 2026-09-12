"""Serializers du module ``apps.datarooms`` (groupe NTDOC, P2).

RAPPEL multi-tenant : ``company`` n'est JAMAIS exposée en écriture — elle est
posée côté serveur par ``CompanyScopedModelViewSet.perform_create``.
"""
from rest_framework import serializers

from core.mixins import SameCompanyFKSerializerMixin

from .models import SalleDeDonnees, SalleDeDonneesDocument


class SalleDeDonneesDocumentSerializer(SameCompanyFKSerializerMixin,
                                       serializers.ModelSerializer):
    """Une ligne d'appartenance document ↔ salle.

    AUD601 — ``document`` est une FK CROSS-APP vers un modèle scopé société :
    elle est validée même-société de façon déclarative (sans quoi un id de la
    société voisine passerait, DRF acceptant n'importe quelle clé primaire)."""

    same_company_fields = ('document',)

    document_nom = serializers.SerializerMethodField()
    statut_libelle = serializers.SerializerMethodField()

    class Meta:
        model = SalleDeDonneesDocument
        fields = [
            'id', 'salle', 'document', 'document_nom', 'ordre', 'visible',
            'statut_libelle', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_document_nom(self, obj) -> str:
        return getattr(obj.document, 'nom', '') or ''

    def get_statut_libelle(self, obj) -> str:
        return 'Visible' if obj.visible else 'Masqué'

    def validate(self, attrs):
        """Salle et document doivent appartenir à la MÊME société.

        Complète la garde déclarative ``same_company_fields`` : celle-ci borne
        le document à la société de l'APPELANT, celle-ci le borne à la société
        de la SALLE (les deux coïncident en pratique, mais un service appelé
        hors requête n'a pas d'appelant)."""
        salle = attrs.get('salle') or getattr(self.instance, 'salle', None)
        document = attrs.get('document') or getattr(
            self.instance, 'document', None)
        if salle is not None and document is not None:
            if salle.company_id != getattr(document, 'company_id', None):
                raise serializers.ValidationError(
                    "Ce document n'appartient pas à la société de la salle.")
        return attrs


class SalleDeDonneesSerializer(SameCompanyFKSerializerMixin,
                               serializers.ModelSerializer):
    """Fiche d'une salle de données.

    AUD601 — ``dossier_source`` est une FK cross-app (``ged.Folder``) scopée
    société : validée même-société de façon déclarative."""

    same_company_fields = ('dossier_source',)

    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)
    nombre_documents = serializers.SerializerMethodField()

    class Meta:
        model = SalleDeDonnees
        fields = [
            'id', 'nom', 'description', 'dossier_source', 'deal_type',
            'statut', 'statut_libelle', 'expires_at', 'nombre_documents',
            'created_at', 'updated_at',
        ]
        # `statut` ne change que par l'action de fermeture (NTDOC16) : un PATCH
        # brut ne doit jamais court-circuiter la révocation des accès.
        read_only_fields = ['statut', 'created_at', 'updated_at']

    def get_nombre_documents(self, obj) -> int:
        return obj.documents.count()
