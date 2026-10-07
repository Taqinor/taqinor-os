"""VT2 — sérialiseurs de la visite technique terrain.

Portée VOLONTAIREMENT étroite : ce module ne sert QUE l'ÉCRITURE de l'entête
d'une visite (création / édition des champs libres). La LECTURE passe
intégralement par ``selectors.contexte_visite_terrain`` — l'agrégat du contrat
PACT10 est la seule forme servie en lecture, jamais un second rendu qui
divergerait en silence.

``statut`` est READ-ONLY (AUD515) : il ne change que par les transitions
dédiées (``terminer``/``valider``/``renvoyer``), jamais par un PATCH de champ.
"""
from rest_framework import serializers

from .models import VisiteTerrain


class VisiteTerrainSerializer(serializers.ModelSerializer):
    """Entête d'une visite : lead, commercial, date prévue, notes."""

    class Meta:
        model = VisiteTerrain
        fields = [
            'id', 'lead', 'commercial', 'statut', 'date_prevue',
            'date_realisee', 'notes',
        ]
        read_only_fields = [
            'id', 'statut', 'date_realisee',
        ]

    def validate_lead(self, value):
        """Le lead doit appartenir à la société de l'appelant (multi-tenant)."""
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                "Ce lead n'appartient pas à votre société.")
        # ALEA11 — le dossier d'une visite est FIGÉ après sa création : ses
        # photos sont des pièces jointes du lead d'origine et ses événements
        # ont déjà atteint ce lead ; la déplacer laisserait les deux derrière.
        if self.instance is not None and value.pk != self.instance.lead_id:
            raise serializers.ValidationError(
                "Le dossier d'une visite ne se change pas : créez une "
                'nouvelle visite.')
        return value

    def validate_date_prevue(self, value):
        """ALEA10 — en ÉDITION, la date prévue ne bouge que sur une visite
        BROUILLON et jamais vers le passé (validateur partagé avec
        ``services.planifier_visite``). À la création, les gardes vivent dans
        ``planifier_visite`` (qui les rapporte avec celle du commercial)."""
        if self.instance is None:
            return value
        from . import services

        message = services.erreur_modification_date_prevue(self.instance,
                                                           value)
        if message:
            raise serializers.ValidationError(message)
        return value

    def validate_commercial(self, value):
        if value is None:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                "Ce commercial n'appartient pas à votre société.")
        return value


class VisiteRenvoiSerializer(serializers.Serializer):
    """VT3 — corps de l'action ``renvoyer`` (motif OBLIGATOIRE)."""

    photos = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list)
    mesures = serializers.ListField(
        child=serializers.DictField(), required=False, default=list)
    motif = serializers.CharField(allow_blank=False)

    def validate_motif(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError(
                'Le motif du renvoi est obligatoire : le commercial doit '
                'savoir exactement quoi refaire.')
        return value.strip()
