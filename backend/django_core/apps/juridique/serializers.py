"""Serializers du module ``apps.juridique`` (groupe NTJUR).

RAPPEL multi-tenant : ``company`` n'est JAMAIS exposée en écriture — elle est
posée côté serveur par ``CompanyScopedModelViewSet.perform_create``.

``reference`` et ``statut`` sont en lecture seule : la référence vient de
``core.numbering`` (anti-collision) et le statut ne change que par les actions
de la machine à états (``services.changer_statut``) — un PATCH brut ne doit
jamais court-circuiter les gardes métier (AUD515).
"""
from rest_framework import serializers

from .models import DossierJuridique


class DossierJuridiqueSerializer(serializers.ModelSerializer):
    """Fiche d'un dossier juridique."""

    responsable_interne_nom = serializers.SerializerMethodField()
    statut_libelle = serializers.CharField(
        source='get_statut_display', read_only=True)
    nature_libelle = serializers.CharField(
        source='get_nature_display', read_only=True)

    class Meta:
        model = DossierJuridique
        fields = [
            'id', 'reference', 'titre', 'nature', 'nature_libelle',
            'type_procedure', 'juridiction_nom', 'juridiction_ville',
            'juridiction_degre', 'montant_en_jeu', 'partie_adverse_nom',
            'notre_position', 'resume_faits', 'date_ouverture',
            'responsable_interne', 'responsable_interne_nom',
            'confidentialite', 'statut', 'statut_libelle',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'reference', 'statut', 'created_at', 'updated_at',
        ]

    def get_responsable_interne_nom(self, obj):
        user = obj.responsable_interne
        if user is None:
            return ''
        nom = f'{user.first_name} {user.last_name}'.strip()
        return nom or user.get_username()

    def validate_responsable_interne(self, value):
        """Le responsable doit appartenir à la MÊME société que le dossier."""
        if value is None:
            return value
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                "Le responsable interne doit appartenir à votre société.")
        return value
