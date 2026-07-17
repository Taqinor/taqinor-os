"""Sérialiseurs du module Immobilier.

``company`` n'est JAMAIS exposée en écriture : elle est posée côté serveur par
``TenantMixin.perform_create`` (jamais lue du corps de requête, cf. CLAUDE.md
multi-tenant).
"""
from rest_framework import serializers

from .models import (
    Bail, Batiment, BudgetCharges, DepenseCharges, EcheanceLoyer,
    ElementEtatLieux, EtatLieuxImmo, Local, Locataire, Niveau,
    PieceEtatLieux, RegularisationCharges, RelanceLoyer, RevisionLoyer, Site,
)


def _company(serializer):
    request = serializer.context.get('request')
    user = getattr(request, 'user', None)
    return getattr(user, 'company', None)


def _check_same_company(serializer, obj, field_label):
    """Refuse une FK pointant vers une ligne d'une AUTRE société — sans quoi le
    queryset non scopé de DRF laisserait un id étranger fuir/écrire de la donnée
    cross-tenant (même garde que ``apps.agriculture`` / ``apps.btp_chantier``)."""
    if obj is None:
        return
    company = _company(serializer)
    if company is not None and obj.company_id != company.id:
        raise serializers.ValidationError(
            {field_label: f"{field_label} introuvable pour votre société."})


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
            'annee_construction', 'plan_ged_document_id',
            'mode_repartition', 'company',
        ]
        read_only_fields = ['id', 'company']

    def validate_site(self, value):
        _check_same_company(self, value, 'site')
        return value


class NiveauSerializer(serializers.ModelSerializer):
    batiment_nom = serializers.CharField(source='batiment.nom', read_only=True)

    class Meta:
        model = Niveau
        fields = [
            'id', 'batiment', 'batiment_nom', 'numero', 'ordre', 'company',
        ]
        read_only_fields = ['id', 'company']

    def validate_batiment(self, value):
        _check_same_company(self, value, 'batiment')
        return value


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

    def validate_niveau(self, value):
        _check_same_company(self, value, 'niveau')
        return value


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

    def validate_bail(self, value):
        _check_same_company(self, value, 'bail')
        return value


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

    def validate_local(self, value):
        _check_same_company(self, value, 'local')
        return value

    def validate_locataire(self, value):
        _check_same_company(self, value, 'locataire')
        return value


class EcheanceLoyerSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    bail_local_reference = serializers.CharField(
        source='bail.local.reference', read_only=True)
    bail_locataire_nom = serializers.CharField(
        source='bail.locataire.nom', read_only=True)

    class Meta:
        model = EcheanceLoyer
        fields = [
            'id', 'bail', 'bail_local_reference', 'bail_locataire_nom',
            'periode_debut', 'periode_fin', 'montant_loyer_ht',
            'montant_charges', 'montant_total', 'statut', 'statut_display',
            'facture_ventes_id', 'date_emission_quittance', 'date_creation',
            'company',
        ]
        read_only_fields = [
            'id', 'montant_loyer_ht', 'montant_charges', 'montant_total',
            'statut', 'facture_ventes_id', 'date_emission_quittance',
            'date_creation', 'company',
        ]

    def validate_bail(self, value):
        _check_same_company(self, value, 'bail')
        return value


class RelanceLoyerSerializer(serializers.ModelSerializer):
    canal_display = serializers.CharField(
        source='get_canal_display', read_only=True)

    class Meta:
        model = RelanceLoyer
        fields = [
            'id', 'echeance_loyer', 'niveau', 'date_envoi', 'canal',
            'canal_display', 'template_utilise', 'company',
        ]
        read_only_fields = ['id', 'niveau', 'date_envoi', 'company']

    def validate_echeance_loyer(self, value):
        _check_same_company(self, value, 'echeance_loyer')
        return value


class BudgetChargesSerializer(serializers.ModelSerializer):
    """NTPRO10 — Budget de charges par bâtiment/exercice/poste."""
    poste_display = serializers.CharField(
        source='get_poste_display', read_only=True)
    batiment_nom = serializers.CharField(
        source='batiment.nom', read_only=True)

    class Meta:
        model = BudgetCharges
        fields = [
            'id', 'batiment', 'batiment_nom', 'exercice', 'poste',
            'poste_display', 'montant_budgete_annuel', 'date_creation',
            'company',
        ]
        read_only_fields = ['id', 'date_creation', 'company']

    def validate_batiment(self, value):
        _check_same_company(self, value, 'batiment')
        return value


class DepenseChargesSerializer(serializers.ModelSerializer):
    """NTPRO11 — Dépense réelle rattachée à un budget de charges."""
    budget_poste = serializers.CharField(
        source='budget_charges.poste', read_only=True)
    budget_batiment = serializers.CharField(
        source='budget_charges.batiment.nom', read_only=True)

    class Meta:
        model = DepenseCharges
        fields = [
            'id', 'budget_charges', 'budget_poste', 'budget_batiment',
            'date', 'montant_reel', 'facture_fournisseur_id',
            'ged_document_id', 'date_creation', 'company',
        ]
        read_only_fields = ['id', 'date_creation', 'company']

    def validate_budget_charges(self, value):
        _check_same_company(self, value, 'budget_charges')
        return value


class RegularisationChargesSerializer(serializers.ModelSerializer):
    """NTPRO13 — Régularisation annuelle des charges d'un bail (LECTURE
    SEULE côté API : une ligne naît TOUJOURS de `generer_regularisation`,
    jamais d'un POST libre)."""
    sens_display = serializers.CharField(
        source='get_sens_display', read_only=True)
    bail_local_reference = serializers.CharField(
        source='bail.local.reference', read_only=True)
    bail_locataire_nom = serializers.CharField(
        source='bail.locataire.nom', read_only=True)

    class Meta:
        model = RegularisationCharges
        fields = [
            'id', 'bail', 'bail_local_reference', 'bail_locataire_nom',
            'exercice', 'provisions_encaissees', 'quote_part_reelle',
            'solde', 'sens', 'sens_display', 'facture_ventes_id',
            'avoir_ventes_id', 'date_emission', 'date_creation', 'company',
        ]
        read_only_fields = fields


class ElementEtatLieuxSerializer(serializers.ModelSerializer):
    """NTPRO15 — Élément inspecté d'une pièce (sol/murs/plafond/…)."""
    etat_display = serializers.CharField(
        source='get_etat_display', read_only=True)

    class Meta:
        model = ElementEtatLieux
        fields = [
            'id', 'piece', 'element', 'etat', 'etat_display', 'commentaire',
            'ordre', 'company',
        ]
        read_only_fields = ['id', 'company']

    def validate_piece(self, value):
        _check_same_company(self, value, 'piece')
        return value


class PieceEtatLieuxSerializer(serializers.ModelSerializer):
    """NTPRO15 — Pièce inspectée d'un état des lieux (+ éléments imbriqués)."""
    etat_general_display = serializers.CharField(
        source='get_etat_general_display', read_only=True)
    elements = ElementEtatLieuxSerializer(many=True, read_only=True)

    class Meta:
        model = PieceEtatLieux
        fields = [
            'id', 'etat_lieux', 'nom_piece', 'etat_general',
            'etat_general_display', 'commentaire', 'ordre', 'elements',
            'company',
        ]
        read_only_fields = ['id', 'company']

    def validate_etat_lieux(self, value):
        _check_same_company(self, value, 'etat_lieux')
        return value


class EtatLieuxImmoSerializer(serializers.ModelSerializer):
    """NTPRO15 — État des lieux (+ pièces/éléments imbriqués, pré-remplis
    depuis la grille standard du type de local à la création)."""
    moment_display = serializers.CharField(
        source='get_moment_display', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    bail_local_reference = serializers.CharField(
        source='bail.local.reference', read_only=True)
    pieces = PieceEtatLieuxSerializer(many=True, read_only=True)

    class Meta:
        model = EtatLieuxImmo
        fields = [
            'id', 'bail', 'bail_local_reference', 'moment', 'moment_display',
            'date', 'statut', 'statut_display', 'technicien', 'pieces',
            'date_creation', 'company',
        ]
        read_only_fields = [
            'id', 'statut', 'pieces', 'date_creation', 'company',
        ]

    def validate_bail(self, value):
        _check_same_company(self, value, 'bail')
        return value
