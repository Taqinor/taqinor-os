"""Sérialiseur du catalogue « Réalisations » (Paramètres → Réalisations).

``company`` n'est JAMAIS un champ du sérialiseur : elle est forcée côté
serveur par ``CompanyScopedModelViewSet`` (socle ARC2), jamais lue du corps de
la requête.

``date_creation`` est le ``created_at`` du socle ``TenantModel`` (ARC1), exposé
sous son nom métier : aucune colonne d'horodatage n'est dupliquée.
"""
from rest_framework import serializers

from .models_realisations import Realisation


class RealisationSerializer(serializers.ModelSerializer):
    """Une installation réelle de la société + sa page publique."""

    date_creation = serializers.DateTimeField(
        source='created_at', read_only=True)

    class Meta:
        model = Realisation
        fields = [
            'id', 'titre', 'ville', 'puissance_kwc', 'mise_en_service',
            'url_page', 'lien_suivi', 'actif', 'date_creation',
        ]

    def validate_titre(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Le titre est requis.')
        return value

    def validate_ville(self, value):
        # Le texte est conservé tel quel ici : c'est le modèle qui le passe au
        # gazetier à l'enregistrement (``Realisation.save``), pour que TOUS les
        # chemins d'écriture (API, ORM, import) canonisent de la même façon.
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('La ville est requise.')
        return value

    def validate_url_page(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError(
                'Le lien de la page de la réalisation est requis : sans lui, '
                'le message ne peut apporter aucune preuve.')
        return value
