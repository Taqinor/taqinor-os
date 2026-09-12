"""Sérialiseurs de l'app ESG (Groupe NTESG).

``company`` n'est jamais exposée en écriture : posée côté serveur par
``core.viewsets.CompanyScopedModelViewSet`` (``TenantMixin``). Le ``statut``
d'une ``PeriodeReportingESG`` ne se modifie jamais par PATCH direct — il ne
change que via l'action ``figer`` (machine à états à sens unique, NTESG1).
"""
from rest_framework import serializers

from django.core.exceptions import ValidationError as DjangoValidationError

from .models import (
    CatalogueIndicateurESG, DocumentPolitiqueESG, FacteurEmissionReference,
    ObjectifESGTrajectoire, ParametresESG, PartiePrenanteESG,
    PeriodeReportingESG, SnapshotESG,
)


class SnapshotESGSerializer(serializers.ModelSerializer):
    class Meta:
        model = SnapshotESG
        fields = ['id', 'periode', 'donnees', 'figee_le']
        read_only_fields = fields


class PeriodeReportingESGSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    figee_par_nom = serializers.SerializerMethodField()
    est_figee = serializers.BooleanField(read_only=True)

    class Meta:
        model = PeriodeReportingESG
        fields = [
            'id', 'libelle', 'date_debut', 'date_fin', 'statut',
            'statut_display', 'est_figee', 'figee_le', 'figee_par',
            'figee_par_nom', 'created_at', 'updated_at',
        ]
        # Le statut/figeage passe EXCLUSIVEMENT par l'action ``figer`` — pas
        # de PATCH direct qui contournerait le service (et son gel du
        # snapshot).
        read_only_fields = [
            'statut', 'figee_le', 'figee_par', 'created_at', 'updated_at',
        ]

    def get_figee_par_nom(self, obj):
        return getattr(obj.figee_par, 'username', None)

    def validate(self, attrs):
        date_debut = attrs.get(
            'date_debut', getattr(self.instance, 'date_debut', None))
        date_fin = attrs.get(
            'date_fin', getattr(self.instance, 'date_fin', None))
        if date_debut and date_fin and date_fin < date_debut:
            raise serializers.ValidationError(
                {'date_fin': (
                    'La date de fin ne peut pas précéder la date de '
                    'début.')})
        # ``company`` n'étant pas un champ du sérialiseur (posée côté
        # serveur), le validateur unique_together AUTOMATIQUE de DRF ne
        # couvre pas la contrainte ``esg_periode_co_libelle_uniq`` (elle
        # inclut ``company``) — vérification explicite pour renvoyer 400
        # plutôt qu'un ``IntegrityError`` (500).
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        libelle = attrs.get('libelle', getattr(self.instance, 'libelle', None))
        if company is not None and libelle:
            qs = PeriodeReportingESG.objects.filter(
                company=company, libelle=libelle)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'libelle': (
                        'Une période avec ce libellé existe déjà pour '
                        'cette société.')})
        return attrs


class CatalogueIndicateurESGSerializer(serializers.ModelSerializer):
    pilier_display = serializers.CharField(
        source='get_pilier_display', read_only=True)

    class Meta:
        model = CatalogueIndicateurESG
        fields = [
            'id', 'code', 'libelle', 'pilier', 'pilier_display',
            'unite_attendue', 'reference_gri',
        ]
        # Référentiel seedé — lecture seule côté API (voir
        # CatalogueIndicateurESGViewSet, ReadOnlyModelViewSet).
        read_only_fields = fields


class ObjectifESGTrajectoireSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObjectifESGTrajectoire
        fields = [
            'id', 'indicateur_code', 'libelle', 'valeur_reference',
            'annee_reference', 'valeur_cible', 'annee_cible', 'jalons',
            'actif', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        annee_ref = attrs.get(
            'annee_reference', getattr(self.instance, 'annee_reference', None))
        annee_cible = attrs.get(
            'annee_cible', getattr(self.instance, 'annee_cible', None))
        if annee_ref and annee_cible and annee_cible <= annee_ref:
            raise serializers.ValidationError(
                {'annee_cible': (
                    "L'année cible doit être postérieure à l'année de "
                    'référence.')})
        # ``company`` n'étant pas un champ du sérialiseur, le validateur
        # unique_together automatique de DRF ne couvre pas la contrainte
        # ``esg_objectif_co_code_anneecible_uniq`` — vérification explicite
        # (400 propre plutôt qu'un ``IntegrityError`` 500).
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        code = attrs.get(
            'indicateur_code', getattr(self.instance, 'indicateur_code', None))
        if company is not None and code and annee_cible:
            qs = ObjectifESGTrajectoire.objects.filter(
                company=company, indicateur_code=code, annee_cible=annee_cible)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'indicateur_code': (
                        'Un objectif existe déjà pour cet indicateur et '
                        'cette année cible.')})
        return attrs


class PartiePrenanteESGSerializer(serializers.ModelSerializer):
    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True)

    class Meta:
        model = PartiePrenanteESG
        fields = [
            'id', 'nom', 'categorie', 'categorie_display', 'enjeux',
            'influence', 'interet', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class DocumentPolitiqueESGSerializer(serializers.ModelSerializer):
    type_document_display = serializers.CharField(
        source='get_type_document_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = DocumentPolitiqueESG
        fields = [
            'id', 'libelle', 'type_document', 'type_document_display',
            'statut', 'statut_display', 'date_publication', 'date_revue',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class FacteurEmissionReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacteurEmissionReference
        fields = [
            'id', 'categorie', 'unite', 'valeur', 'source', 'date_maj',
            'version', 'actif', 'created_at', 'updated_at',
        ]
        # `version`/`actif` sont posés SERVEUR par
        # `services.creer_version_facteur` (jamais un écrasement silencieux
        # côté client) — voir `FacteurEmissionReferenceViewSet.perform_create`.
        read_only_fields = ['version', 'actif', 'created_at', 'updated_at']


class ParametresESGSerializer(serializers.ModelSerializer):
    """NTESG20 — réglages ESG de la société (singleton par tenant)."""

    frequence_reporting_display = serializers.CharField(
        source='get_frequence_reporting_display', read_only=True)
    pilote_esg_nom = serializers.SerializerMethodField()

    class Meta:
        model = ParametresESG
        fields = [
            'id', 'seuil_alerte_derive_pct', 'pilote_esg', 'pilote_esg_nom',
            'frequence_reporting', 'frequence_reporting_display',
            'ponderation_badge_maturite', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def get_pilote_esg_nom(self, obj):
        pilote = obj.pilote_esg
        if pilote is None:
            return ''
        complet = (getattr(pilote, 'get_full_name', lambda: '')() or '').strip()
        return complet or getattr(pilote, 'username', '')

    def validate_pilote_esg(self, value):
        """Le pilote appartient à la MÊME société (jamais un compte voisin)."""
        if value is None:
            return value
        company = getattr(self.instance, 'company', None)
        if company is not None and getattr(value, 'company_id', None) != company.id:
            raise serializers.ValidationError(
                "Le pilote ESG doit appartenir à votre société.")
        return value

    def validate_ponderation_badge_maturite(self, value):
        """Rejoue la validation du MODÈLE — un seul jeu de règles, ici traduit
        en 400 au lieu d'une 500, et le message NOMME la composante fautive."""
        sonde = ParametresESG(
            company=getattr(self.instance, 'company', None),
            ponderation_badge_maturite=value)
        try:
            sonde.clean()
        except DjangoValidationError as exc:
            messages = exc.message_dict.get(
                'ponderation_badge_maturite', exc.messages)
            raise serializers.ValidationError(messages)
        return value
