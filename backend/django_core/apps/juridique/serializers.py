"""Serializers du module ``apps.juridique`` (groupe NTJUR).

RAPPEL multi-tenant : ``company`` n'est JAMAIS exposée en écriture — elle est
posée côté serveur par ``CompanyScopedModelViewSet.perform_create``.

``reference`` et ``statut`` sont en lecture seule : la référence vient de
``core.numbering`` (anti-collision) et le statut ne change que par les actions
de la machine à états (``services.changer_statut``) — un PATCH brut ne doit
jamais court-circuiter les gardes métier (AUD515).
"""
from rest_framework import serializers

from .models import (
    CabinetAvocat, DossierJuridique, EtapeApprobationJuridique, MandatAvocat,
    RegleApprobationJuridique,
)


def _company_de(serializer):
    """Société de l'appelant (posée côté serveur), ou ``None`` hors requête."""
    request = serializer.context.get('request')
    return getattr(getattr(request, 'user', None), 'company', None)


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
        company = _company_de(self)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                "Le responsable interne doit appartenir à votre société.")
        return value


class CabinetAvocatSerializer(serializers.ModelSerializer):
    """Fiche d'un cabinet d'avocats externe (NTJUR9)."""

    class Meta:
        model = CabinetAvocat
        fields = [
            'id', 'nom', 'barreau', 'specialites', 'contact_principal',
            'email', 'telephone', 'taux_horaire_moyen', 'actif',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class MandatAvocatSerializer(serializers.ModelSerializer):
    """Mandat confié à un cabinet sur un dossier (NTJUR10/NTJUR19).

    ``statut`` est en LECTURE SEULE : il n'avance que par les actions gardées
    (``lancer-approbation-mandat`` / ``activer``) — un PATCH brut ne doit
    jamais poser ``actif`` en contournant le seuil d'approbation.
    """

    cabinet_nom = serializers.CharField(source='cabinet.nom', read_only=True)
    montant_engage = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = MandatAvocat
        fields = [
            'id', 'dossier', 'cabinet', 'cabinet_nom', 'date_mandat',
            'mode_facturation', 'montant_forfait', 'taux_horaire',
            'heures_estimees', 'pourcentage_resultat', 'montant_engage',
            'statut', 'created_at', 'updated_at',
        ]
        read_only_fields = ['statut', 'created_at', 'updated_at']

    def validate_dossier(self, value):
        company = _company_de(self)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                "Ce dossier juridique n'appartient pas à votre société.")
        return value

    def validate_cabinet(self, value):
        company = _company_de(self)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                "Ce cabinet d'avocats n'appartient pas à votre société.")
        return value

    def validate(self, attrs):
        """Cohérence du mode de facturation avec les montants saisis."""
        mode = attrs.get(
            'mode_facturation',
            getattr(self.instance, 'mode_facturation', None))
        forfait = attrs.get(
            'montant_forfait', getattr(self.instance, 'montant_forfait', None))
        taux = attrs.get(
            'taux_horaire', getattr(self.instance, 'taux_horaire', None))
        if mode == MandatAvocat.ModeFacturation.FORFAIT and forfait is None:
            raise serializers.ValidationError(
                {'montant_forfait': 'Renseignez le montant du forfait pour un '
                                    'mandat au forfait.'})
        if mode == MandatAvocat.ModeFacturation.HORAIRE and taux is None:
            raise serializers.ValidationError(
                {'taux_horaire': 'Renseignez le taux horaire pour un mandat '
                                 'facturé à l\'heure.'})
        return attrs


class RegleApprobationJuridiqueSerializer(serializers.ModelSerializer):
    """Règle d'approbation d'un engagement de dépense juridique (NTJUR19)."""

    class Meta:
        model = RegleApprobationJuridique
        fields = [
            'id', 'libelle', 'nature_dossier', 'montant_min', 'montant_max',
            'niveau_approbation', 'nombre_approbateurs', 'priorite', 'actif',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        mini = attrs.get('montant_min',
                         getattr(self.instance, 'montant_min', None))
        maxi = attrs.get('montant_max',
                         getattr(self.instance, 'montant_max', None))
        if mini is not None and maxi is not None and mini > maxi:
            raise serializers.ValidationError(
                {'montant_min': 'Le montant minimum ne peut pas dépasser le '
                                'montant maximum.'})
        return attrs


class EtapeApprobationJuridiqueSerializer(serializers.ModelSerializer):
    """Étape d'un workflow d'approbation de mandat (lecture seule côté API :
    les décisions passent par les actions ``approuver-etape`` /
    ``rejeter-etape``)."""

    approbateur_nom = serializers.SerializerMethodField()

    class Meta:
        model = EtapeApprobationJuridique
        fields = [
            'id', 'mandat', 'regle', 'niveau', 'niveau_approbation',
            'approbateur', 'approbateur_nom', 'statut', 'decision_le',
            'commentaire', 'created_at',
        ]
        read_only_fields = fields

    def get_approbateur_nom(self, obj):
        user = obj.approbateur
        if user is None:
            return ''
        return f'{user.first_name} {user.last_name}'.strip() or \
            user.get_username()
