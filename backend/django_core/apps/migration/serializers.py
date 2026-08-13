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

from .models import (
    LotMigration, PlaybookInstance, ProjetMigration, RapportReconciliation)


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


class PlaybookInstanceSerializer(serializers.ModelSerializer):
    """NTMIG22 — instance d'un playbook kb pour un déploiement.

    ``etapes`` est un INSTANTANÉ posé côté serveur à l'instanciation : le
    laisser modifiable permettrait de réécrire le dénominateur de la
    progression après coup (ajouter/retirer des cases pour « atteindre »
    100 %). ``avancement`` ne se pose que par l'action ``cocher`` (clé
    validée), jamais par un PATCH libre qui accepterait des cases fantômes.
    """

    progression = serializers.SerializerMethodField()
    nb_etapes = serializers.SerializerMethodField()
    nb_faites = serializers.SerializerMethodField()
    # NTMIG22 — le playbook modèle est CHOISI à la création (via l'action
    # ``instancier``) ; le rattacher après coup à un autre article laisserait
    # un instantané d'étapes qui ne correspond plus au playbook cité.
    playbook_article = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = PlaybookInstance
        fields = [
            'id', 'playbook_article', 'playbook_titre', 'projet_migration',
            'client_final', 'etapes', 'avancement', 'statut', 'responsable',
            'progression', 'nb_etapes', 'nb_faites',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'playbook_article', 'playbook_titre', 'etapes',
            'avancement', 'statut', 'progression', 'nb_etapes', 'nb_faites',
            'created_at', 'updated_at',
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_progression(self, obj):
        return obj.progression

    @extend_schema_field(serializers.IntegerField())
    def get_nb_etapes(self, obj):
        return obj.nb_etapes

    @extend_schema_field(serializers.IntegerField())
    def get_nb_faites(self, obj):
        return obj.nb_faites

    def validate_projet_migration(self, value):
        """Le projet cité doit appartenir à la société de l'appelant.

        Le queryset scopé ne protège que la LECTURE : sans ce contrôle, une
        instance pourrait se greffer sur le projet d'une autre société.
        """
        request = self.context.get('request')
        if value is not None and request is not None \
                and value.company_id != request.user.company_id:
            raise serializers.ValidationError('Projet introuvable.')
        return value

    def validate_responsable(self, value):
        request = self.context.get('request')
        if value is not None and request is not None \
                and getattr(value, 'company_id', None) \
                != request.user.company_id:
            raise serializers.ValidationError('Responsable introuvable.')
        return value
