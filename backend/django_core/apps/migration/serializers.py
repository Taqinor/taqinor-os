"""Serializers DRF du groupe NTMIG.

``company`` n'est JAMAIS exposé (elle est forcée côté serveur par
``CompanyScopedModelViewSet``) ; les compteurs, statuts et champs de dérogation
sont en lecture seule — ils ne se posent que par les services (garde NTMIG5),
jamais par le corps d'une requête.

Certains champs sont volontairement **modifiables à la création puis figés** :
déplacer un lot d'un projet à l'autre, ou changer l'entité/la source APRÈS un
chargement, ferait mentir la réconciliation et le PV (les compteurs d'un
chargement seraient rapportés sous une autre entité, et un projet pourrait se
voir attribuer le lot d'une autre société). ``_CreationSeulementMixin`` met ces
champs en lecture seule dès que l'instance existe.
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import LotMigration, ProjetMigration, RapportReconciliation


class _CreationSeulementMixin:
    """Rend `creation_seulement` en lecture seule sur une mise à jour."""

    creation_seulement = ()

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            for nom in self.creation_seulement:
                if nom in fields:
                    fields[nom].read_only = True
        return fields


class RapportReconciliationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RapportReconciliation
        fields = [
            'id', 'lot', 'nb_source', 'nb_cible_crees', 'nb_cible_existants',
            'nb_erreurs', 'total_financier_source', 'total_financier_cible',
            'ecart_financier', 'ecarts', 'conforme', 'created_at',
        ]
        read_only_fields = fields


class LotMigrationSerializer(_CreationSeulementMixin,
                             serializers.ModelSerializer):
    # `projet` et `entite` définissent CE QUE le lot a chargé : les figer après
    # création empêche de rattacher un lot au projet d'une autre société et
    # d'attribuer des compteurs de chargement à la mauvaise entité.
    creation_seulement = ('projet', 'entite')

    dernier_rapport = serializers.SerializerMethodField()
    derogation_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = LotMigration
        fields = [
            'id', 'projet', 'entite', 'ordre', 'statut', 'import_job',
            'source_lignes', 'crees', 'maj', 'erreurs', 'source_montant',
            'derogation_reconcile', 'derogation_motif', 'derogation_par_nom',
            'derogation_at', 'dernier_rapport', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'import_job', 'source_lignes', 'crees', 'maj',
            'erreurs', 'source_montant', 'derogation_reconcile',
            'derogation_motif', 'derogation_par_nom', 'derogation_at',
            'dernier_rapport', 'created_at', 'updated_at',
        ]

    def validate_entite(self, value):
        """L'entité doit être une cible d'import RÉELLE.

        Sans ce contrôle, on crée un lot que rien ne pourra jamais charger, et
        l'erreur ne surgit qu'à l'étape « Analyser » — avec un message du
        moteur d'import au lieu du champ fautif.
        """
        from apps.dataimport import services as dataimport_services

        if value not in dataimport_services.TARGETS:
            cibles = ', '.join(sorted(dataimport_services.TARGETS))
            raise serializers.ValidationError(
                f"Entité inconnue. Cibles disponibles : {cibles}.")
        return value

    @extend_schema_field(RapportReconciliationSerializer(allow_null=True))
    def get_dernier_rapport(self, obj):
        rapport = obj.rapports.order_by('-created_at').first()
        if rapport is None:
            return None
        return RapportReconciliationSerializer(rapport).data

    @extend_schema_field(serializers.CharField())
    def get_derogation_par_nom(self, obj):
        return getattr(obj.derogation_par, 'username', '') or ''


class ProjetMigrationSerializer(_CreationSeulementMixin,
                                serializers.ModelSerializer):
    # La source détermine l'espace de noms `ExternalRef` du projet : la changer
    # après un chargement orphelinerait les références déjà posées, et le
    # ré-import se remettrait à créer des doublons.
    creation_seulement = ('source',)

    lots_total = serializers.SerializerMethodField()
    lots_reconcilies = serializers.SerializerMethodField()

    class Meta:
        model = ProjetMigration
        fields = [
            'id', 'nom', 'source', 'statut', 'cree_par', 'date_debut',
            'date_fin', 'notes', 'lots_total', 'lots_reconcilies',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'cree_par', 'date_fin', 'lots_total',
            'lots_reconcilies', 'created_at', 'updated_at',
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_lots_total(self, obj):
        return obj.lots.filter(company_id=obj.company_id).count()

    @extend_schema_field(serializers.IntegerField())
    def get_lots_reconcilies(self, obj):
        return obj.lots.filter(
            company_id=obj.company_id,
            statut=LotMigration.Statut.RECONCILIE).count()
