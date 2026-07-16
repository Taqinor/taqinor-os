"""Sérialiseurs du module Immobilier.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
``TenantMixin.perform_create`` (jamais lue du corps de requête, cf. CLAUDE.md
multi-tenant).
"""
from rest_framework import serializers

from .models import Bail, Batiment, Local, Locataire, Niveau, RevisionLoyer, Site


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = [
            'id', 'nom', 'adresse', 'ville', 'gps_lat', 'gps_lng',
            'date_creation', 'company',
        ]
        read_only_fields = ['id', 'date_creation', 'company']


class BatimentSerializer(serializers.ModelSerializer):
    site_nom = serializers.CharField(source='site.nom', read_only=True)

    class Meta:
        model = Batiment
        fields = [
            'id', 'site', 'site_nom', 'nom', 'nb_niveaux',
            'annee_construction', 'plan_ged_document_id', 'company',
        ]
        read_only_fields = ['id', 'company']


class NiveauSerializer(serializers.ModelSerializer):
    batiment_nom = serializers.CharField(source='batiment.nom', read_only=True)

    class Meta:
        model = Niveau
        fields = [
            'id', 'batiment', 'batiment_nom', 'numero', 'ordre', 'company',
        ]
        read_only_fields = ['id', 'company']


class LocalSerializer(serializers.ModelSerializer):
    type_local_display = serializers.CharField(
        source='get_type_local_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    niveau_numero = serializers.CharField(
        source='niveau.numero', read_only=True)

    class Meta:
        model = Local
        fields = [
            'id', 'niveau', 'niveau_numero', 'reference', 'type_local',
            'type_local_display', 'surface_m2', 'tantiemes', 'statut',
            'statut_display', 'company',
        ]
        read_only_fields = ['id', 'company']


class LocataireSerializer(serializers.ModelSerializer):
    type_locataire_display = serializers.CharField(
        source='get_type_locataire_display', read_only=True)

    class Meta:
        model = Locataire
        fields = [
            'id', 'type_locataire', 'type_locataire_display', 'nom', 'cin',
            'ice', 'telephone', 'email', 'adresse', 'client_ventes_id',
            'date_creation', 'company',
        ]
        read_only_fields = ['id', 'client_ventes_id', 'date_creation', 'company']


class RevisionLoyerSerializer(serializers.ModelSerializer):
    class Meta:
        model = RevisionLoyer
        fields = [
            'id', 'bail', 'date_effet', 'ancien_loyer', 'nouveau_loyer',
            'indice', 'taux_variation', 'date_creation', 'company',
        ]
        read_only_fields = [
            'id', 'ancien_loyer', 'nouveau_loyer', 'taux_variation',
            'date_creation', 'company',
        ]


class BailSerializer(serializers.ModelSerializer):
    type_bail_display = serializers.CharField(
        source='get_type_bail_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    local_reference = serializers.CharField(
        source='local.reference', read_only=True)
    locataire_nom = serializers.CharField(
        source='locataire.nom', read_only=True)
    # NTPRO4 — historique des révisions visible sur le détail du bail.
    revisions = RevisionLoyerSerializer(many=True, read_only=True)

    class Meta:
        model = Bail
        fields = [
            'id', 'local', 'local_reference', 'locataire', 'locataire_nom',
            'type_bail', 'type_bail_display', 'date_debut', 'duree_mois',
            'loyer_mensuel_ht', 'charges_mensuelles_provisions',
            'depot_garantie', 'statut', 'statut_display', 'date_preavis',
            'date_fin_effective', 'bailleur_nom_snapshot',
            'locataire_nom_snapshot', 'depot_garantie_recu',
            'date_reception_depot', 'depot_garantie_restitue',
            'date_restitution', 'montant_retenu', 'motif_retenue',
            'revisions', 'date_creation', 'company',
        ]
        read_only_fields = [
            'id', 'statut', 'bailleur_nom_snapshot', 'locataire_nom_snapshot',
            'depot_garantie_recu', 'date_reception_depot',
            'depot_garantie_restitue', 'date_restitution', 'montant_retenu',
            'motif_retenue', 'date_creation', 'company',
        ]
