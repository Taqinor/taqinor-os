"""Sérialiseurs du module Innovation.

``company`` n'est jamais exposée en écriture : elle est posée côté serveur
(``CompanyScopedModelViewSet.perform_create``/``perform_update``).
``auteur``/``votant``/``created_by`` sont posés côté serveur.
"""
from rest_framework import serializers

from .models import CampagneInnovation, Idee, InnovationSettings, VoteIdee


class IdeeSerializer(serializers.ModelSerializer):
    """Sérialiseur de liste/écriture (NTIDE4) — auteur, votes, contexte."""

    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    auteur_nom = serializers.SerializerMethodField()
    linked_type_display = serializers.CharField(
        source='get_linked_type_display', read_only=True)
    # Exposé sous le nom du domaine (spec NTIDE1) — la colonne DB réelle
    # reste ``created_at`` (héritée de ``core.models.TenantModel``, ARC1).
    date_creation = serializers.DateTimeField(
        source='created_at', read_only=True)

    class Meta:
        model = Idee
        fields = [
            'id', 'titre', 'description', 'contexte', 'statut',
            'statut_display', 'auteur', 'auteur_nom', 'votes_count',
            'linked_type', 'linked_type_display', 'linked_id',
            'date_creation', 'draft', 'archived',
        ]
        # ``statut`` ne se modifie pas par PATCH direct : le cycle de vie
        # passe par les actions de transition (examiner/retenir/réaliser/
        # fermer, NTIDE5) qui appliquent la machine à états et journalisent
        # le chatter. ``votes_count`` est dénormalisé, maintenu par
        # VoteIdeeViewSet — jamais écrit directement. ``draft`` (NTIDE18)
        # suit le même patron : jamais un champ PATCH-able, posé explicitement
        # dans ``perform_create`` (depuis le corps, c'est l'intention même de
        # la case « Enregistrer en brouillon ») puis basculé à False
        # uniquement par l'action ``publier``.
        # ``archived`` (NTIDE19) : jamais PATCH-able non plus, muté
        # uniquement par l'action ``masquer`` (palier Directeur/Responsable).
        read_only_fields = [
            'auteur', 'votes_count', 'statut', 'date_creation', 'draft',
            'archived']

    def get_auteur_nom(self, obj):
        return getattr(obj.auteur, 'username', None)


class IdeeDetailSerializer(IdeeSerializer):
    """Sérialiseur de détail (NTIDE5) — ajoute l'historique (chatter)."""

    historique = serializers.SerializerMethodField()

    class Meta(IdeeSerializer.Meta):
        fields = IdeeSerializer.Meta.fields + ['historique']

    def get_historique(self, obj):
        from apps.records.serializers import ChatterActivitySerializer
        from apps.records.services import chatter_qs

        qs = chatter_qs(obj, company=obj.company)
        return ChatterActivitySerializer(qs, many=True).data


class VoteIdeeSerializer(serializers.ModelSerializer):
    votant_nom = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = VoteIdee
        fields = ['id', 'idee', 'votant', 'votant_nom', 'date']
        read_only_fields = ['votant', 'date']

    def get_votant_nom(self, obj):
        return getattr(obj.votant, 'username', None)


class InnovationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = InnovationSettings
        fields = [
            'campagnes_activees', 'segment_defaut', 'theme_couleur_cta',
            'message_relance', 'seuil_votes_notification',
        ]


class CampagneInnovationSerializer(serializers.ModelSerializer):
    """Sérialiseur de la campagne d'innovation (NTIDE25) — ``statut`` se
    modifie par PATCH direct (contrairement à ``Idee.statut``) : le cycle
    d'une campagne (brouillon→active→fermée) n'a pas de garde métier propre
    par transition, juste une notification au passage à ``active``
    (NTIDE31, côté vue)."""

    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)

    class Meta:
        model = CampagneInnovation
        fields = [
            'id', 'nom', 'description', 'statut', 'statut_display',
            'cible_departement', 'segment', 'date_debut', 'date_fin',
            'message_incitation', 'created_at',
        ]
        read_only_fields = ['created_at']


class IncitationSerializer(serializers.Serializer):
    """NTIDE27 — bandeau d'incitation affiché sur le formulaire « Proposer
    une idée » quand l'utilisateur matche le segment d'une campagne active.
    ``None`` (représenté par ``campagne: null`` côté JSON) si aucune."""

    id = serializers.IntegerField(source='pk')
    nom = serializers.CharField()
    message_incitation = serializers.CharField()
    date_fin = serializers.DateField()
