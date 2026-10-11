"""FG268-FG271 — sérialiseurs du dossier réglementaire (côté ventes).

``company`` et ``created_by`` sont TOUJOURS forcés côté serveur dans les
viewsets, jamais désérialisés. Aucun prix exposé.
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.mixins import SameCompanyFKSerializerMixin

from .models import (
    RegulatoryDossier, DossierChecklistItem, DossierExchange,
    SubventionDossier, Regularisation8221,
)


class DossierChecklistItemSerializer(SameCompanyFKSerializerMixin,
                                     serializers.ModelSerializer):
    """FG268 — pièce/étape de checklist d'un dossier."""
    # ENF17 — dossier d'une AUTRE société = id absent (400).
    same_company_fields = ('dossier',)

    class Meta:
        model = DossierChecklistItem
        fields = [
            'id', 'dossier', 'code', 'libelle', 'etape', 'statut',
            'obligatoire', 'date_echeance', 'relance_due', 'ordre',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class RegulatoryDossierSerializer(SameCompanyFKSerializerMixin,
                                  serializers.ModelSerializer):
    """FG268 — dossier réglementaire de raccordement.

    ASEC26 (C-ASEC-005 site d) — ``chantier`` (FK chaîne vers
    ``installations.Installation``) est BORNÉ à la société de la requête, en
    création comme en mise à jour : l'id d'un chantier d'une autre société ou
    un id absent → 400 sur ``chantier`` (« objet inexistant », aucun libellé
    étranger renvoyé). ENF17 — ``devis`` borné de même (plus « Devis
    inconnu. » de la vue pour le devis d'une autre société)."""
    same_company_fields = ('chantier', 'devis')
    checklist_items = DossierChecklistItemSerializer(
        many=True, read_only=True)
    regime_label = serializers.CharField(
        source='get_regime_8221_display', read_only=True)
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)
    # CIQ617 — bloc ``resume`` du contrat ``dossier_8221.json`` : l'état
    # UNIQUE du dossier, reflété en miroir sur le chantier.
    resume = serializers.SerializerMethodField()
    # CIQ638 — blocs ``regime`` (base légale, guichet) et ``pieces`` (par
    # étape, avec leur source) du contrat ``dossier_8221.json``.
    regime = serializers.SerializerMethodField()
    pieces = serializers.SerializerMethodField()

    class Meta:
        model = RegulatoryDossier
        fields = [
            'id', 'devis', 'chantier', 'regime_8221', 'regime_label',
            'statut', 'statut_label', 'operateur', 'reference_dossier',
            'date_depot', 'date_decision', 'notes',
            # CIQ619 — étude, capacité, convention, exploitation (saisis).
            'etude_frais_notifies_le', 'etude_payee_le', 'etude_conclusion',
            'etude_reglages_imposes', 'capacite_etat', 'capacite_date',
            'convention_signee_le', 'demande_exploitation_le',
            'accord_exploitation_le',
            'checklist_items', 'resume', 'regime', 'pieces',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'regime_label', 'statut_label', 'checklist_items',
            'resume', 'regime', 'pieces', 'created_at', 'updated_at',
        ]

    @extend_schema_field(serializers.DictField())
    def get_resume(self, obj):
        from .selectors import resume_dossier_8221
        return resume_dossier_8221(obj)

    @extend_schema_field(serializers.DictField())
    def get_regime(self, obj):
        from .selectors_reglementaire import regime_contrat_dossier
        return regime_contrat_dossier(obj)

    @extend_schema_field(serializers.ListField(
        child=serializers.DictField()))
    def get_pieces(self, obj):
        from .selectors_reglementaire import pieces_contrat_dossier
        return pieces_contrat_dossier(obj)


class DossierExchangeSerializer(SameCompanyFKSerializerMixin,
                                serializers.ModelSerializer):
    """FG269 — échange de la navette opérateur."""
    # ENF17 — dossier d'une AUTRE société = id absent (400).
    same_company_fields = ('dossier',)
    sens_label = serializers.CharField(
        source='get_sens_display', read_only=True)
    type_label = serializers.CharField(
        source='get_type_echange_display', read_only=True)

    class Meta:
        model = DossierExchange
        fields = [
            'id', 'dossier', 'sens', 'sens_label', 'type_echange',
            'type_label', 'date_echange', 'objet', 'detail',
            'piece_jointe', 'created_at',
        ]
        read_only_fields = [
            'id', 'sens_label', 'type_label', 'created_at',
        ]


class SubventionDossierSerializer(SameCompanyFKSerializerMixin,
                                  serializers.ModelSerializer):
    """FG270 — dossier de subvention/incitation."""
    # ENF17 — devis d'une AUTRE société = id absent (400).
    same_company_fields = ('devis',)
    programme_label = serializers.CharField(
        source='get_programme_display', read_only=True)
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = SubventionDossier
        fields = [
            'id', 'devis', 'programme', 'programme_label', 'statut',
            'statut_label', 'montant_demande', 'montant_accorde',
            'reference', 'eligibilite_note', 'pieces',
            'date_depot', 'date_decision', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'programme_label', 'statut_label',
            'created_at', 'updated_at',
        ]


class Regularisation8221Serializer(SameCompanyFKSerializerMixin,
                                   serializers.ModelSerializer):
    """FG271 — régularisation Article 33 (installation existante).

    ASEC26 — même borne que le dossier réglementaire sur ``chantier`` ;
    ENF17 — et sur ``devis``."""
    same_company_fields = ('chantier', 'devis')

    regime_label = serializers.CharField(
        source='get_regime_8221_display', read_only=True)
    statut_label = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = Regularisation8221
        fields = [
            'id', 'devis', 'chantier', 'regime_8221', 'regime_label',
            'statut', 'statut_label', 'puissance_kwc',
            'date_mise_en_service_initiale', 'declaration_pdf', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'regime_label', 'statut_label',
            'created_at', 'updated_at',
        ]
