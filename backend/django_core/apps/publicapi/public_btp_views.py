"""NTCON31 — ressources BTP/EPC LISIBLES par clé d'API (scope ``read:btp``).

Quatre ressources en LECTURE SEULE, sur la base commune
``public_views.PublicReadOnlyViewSet`` (auth par clé, société TOUJOURS prise
sur la clé, throttle par clé, filtres en liste blanche, ``?updated_since=``) —
aucun nouveau mécanisme d'accès : une MOE ou un maître d'ouvrage externe suit
l'exécution du chantier depuis son propre outil.

CE QUI N'EST JAMAIS EXPOSÉ : le déboursé sec (NTCON11), l'exposition aux
pénalités de retard par lot (NTCON15, ``Lot.penalite_calculee_cache``), le
``prix_achat`` et toute marge. Le décompte général expose ses montants
CONTRACTUELS (marché initial, avenants, situations facturées, retenue de
garantie, solde dû) — ce sont les chiffres que le client signe, pas la marge
de l'entreprise. Le champ ``historique_deverrouillage`` du DGD (NTCON10) est
une trace interne d'administration : jamais servi ici.
"""
from rest_framework import serializers

from apps.btp_chantier.models import (
    RFI, DecompteGeneral, ReserveChantier, VisaDocument,
)

from .constants import SCOPE_READ_BTP
from .public_views import PublicReadOnlyViewSet


class PublicReserveChantierSerializer(serializers.ModelSerializer):
    chantier = serializers.PrimaryKeyRelatedField(read_only=True)
    responsable_leve = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ReserveChantier
        fields = [
            'id', 'chantier', 'lot', 'description', 'gravite', 'statut',
            'responsable_leve', 'date_limite', 'date_levee',
            'motif_contestation', 'archivee',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class PublicRFISerializer(serializers.ModelSerializer):
    chantier = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = RFI
        fields = [
            'id', 'chantier', 'numero', 'question', 'destinataire_texte',
            'statut', 'delai_jours', 'date_limite_reponse',
            'impact_cout', 'impact_delai_jours', 'created_at',
        ]
        read_only_fields = fields


class PublicVisaDocumentSerializer(serializers.ModelSerializer):
    chantier = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = VisaDocument
        fields = [
            'id', 'chantier', 'reference', 'type_visa', 'statut',
            'document_ged_id', 'date_soumission', 'date_revue',
            'observations', 'delai_revue_jours', 'date_limite',
            'nb_resoumissions', 'created_at',
        ]
        read_only_fields = fields


class PublicDecompteGeneralSerializer(serializers.ModelSerializer):
    """Montants CONTRACTUELS uniquement — jamais un coût interne.

    ``historique_deverrouillage`` (NTCON10) est délibérément ABSENT : c'est
    une trace d'administration interne, pas une donnée contractuelle.
    """
    chantier = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = DecompteGeneral
        fields = [
            'id', 'chantier', 'reference', 'statut',
            'montant_marche_initial_ht', 'total_avenants_ht',
            'total_situations_facturees_ht', 'retenue_garantie_montant',
            'solde_du_ht', 'montant_conteste', 'motif_contestation',
            'date_notification', 'date_finalisation',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class PublicReserveChantierViewSet(PublicReadOnlyViewSet):
    """NTCON1/2 — réserves de chantier (punch-list), lecture seule."""
    required_scope = SCOPE_READ_BTP
    serializer_class = PublicReserveChantierSerializer
    queryset = ReserveChantier.objects.select_related(
        'chantier').order_by('-id')
    filter_whitelist = ('chantier', 'statut', 'gravite', 'lot', 'archivee')
    ordering_fields = ('created_at', 'updated_at', 'id')
    sync_field = 'updated_at'


class PublicRFIViewSet(PublicReadOnlyViewSet):
    """NTCON3 — RFI (Request For Information), lecture seule."""
    required_scope = SCOPE_READ_BTP
    serializer_class = PublicRFISerializer
    queryset = RFI.objects.select_related('chantier').order_by('-id')
    filter_whitelist = ('chantier', 'statut', 'numero')
    ordering_fields = ('created_at', 'numero', 'id')
    # RFI n'a pas d'horodatage de modification : la synchro suit la création.
    sync_field = 'created_at'


class PublicVisaDocumentViewSet(PublicReadOnlyViewSet):
    """NTCON5 — visas de documents techniques, lecture seule."""
    required_scope = SCOPE_READ_BTP
    serializer_class = PublicVisaDocumentSerializer
    queryset = VisaDocument.objects.select_related('chantier').order_by('-id')
    filter_whitelist = ('chantier', 'statut', 'type_visa', 'reference')
    ordering_fields = ('created_at', 'date_soumission', 'id')
    sync_field = 'created_at'


class PublicDecompteGeneralViewSet(PublicReadOnlyViewSet):
    """NTCON9/10 — décomptes généraux, lecture seule (montants contractuels)."""
    required_scope = SCOPE_READ_BTP
    serializer_class = PublicDecompteGeneralSerializer
    queryset = DecompteGeneral.objects.select_related(
        'chantier').order_by('-id')
    filter_whitelist = ('chantier', 'statut', 'reference')
    ordering_fields = ('created_at', 'updated_at', 'id')
    sync_field = 'updated_at'
