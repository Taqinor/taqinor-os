from rest_framework import serializers

from .models import (
    CoutStandard, Gamme, OperationGamme, OperationOF, OrdreFabrication,
    OrdreModification, PosteDeCharge, ReservationOF,
)


class PosteDeChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PosteDeCharge
        fields = [
            'id', 'code', 'nom', 'type_poste', 'capacite_heures_jour',
            'cout_horaire', 'calendrier_travail', 'actif', 'sous_traitant',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OperationGammeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationGamme
        fields = [
            'id', 'gamme', 'ordre', 'poste_charge', 'libelle',
            'temps_prepa_min', 'temps_unitaire_min', 'temps_min_par_lot',
        ]
        read_only_fields = ['id']


class GammeSerializer(serializers.ModelSerializer):
    # NTMFG2 — lecture seule imbriquée pour l'écran gamme ; l'écriture des
    # opérations passe par `OperationGammeViewSet` (même convention que
    # `installations.KitViewSet`/`KitComposantViewSet`).
    operations = OperationGammeSerializer(many=True, read_only=True)
    temps_total_prevu_1_unite = serializers.SerializerMethodField()

    class Meta:
        model = Gamme
        fields = [
            'id', 'nom', 'produit', 'version', 'actif', 'kit_source',
            'operations', 'temps_total_prevu_1_unite', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_temps_total_prevu_1_unite(self, obj) -> str:
        from .services import temps_total_gamme
        return str(temps_total_gamme(obj, 1))


class OperationOFSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationOF
        fields = [
            'id', 'ordre_fabrication', 'operation_gamme', 'poste_charge',
            'ordre', 'libelle', 'statut', 'date_planifiee', 'demarree_le',
            'terminee_le', 'temps_reel_min', 'quantite_bonne',
            'quantite_rebut', 'motif_rebut', 'cout_faconnage',
        ]
        read_only_fields = [
            'id', 'statut', 'demarree_le', 'terminee_le', 'temps_reel_min',
            'quantite_bonne', 'quantite_rebut', 'motif_rebut', 'cout_faconnage',
        ]


class ReservationOFSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReservationOF
        fields = [
            'id', 'ordre_fabrication', 'produit', 'quantite', 'consomme',
            'date_creation',
        ]
        read_only_fields = ['id', 'date_creation']


class OrdreFabricationSerializer(serializers.ModelSerializer):
    operations = OperationOFSerializer(many=True, read_only=True)
    reservations = ReservationOFSerializer(many=True, read_only=True)
    # NTMFG9 — confort écran (kanban/liste) : évite un aller-retour produit
    # séparé côté frontend. Lecture seule, dérivée de `produit.nom`.
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)

    class Meta:
        model = OrdreFabrication
        fields = [
            'id', 'produit', 'produit_nom', 'quantite', 'gamme', 'statut',
            'date_debut_planifiee', 'date_fin_planifiee', 'priorite',
            'kit_ordre_assemblage', 'stock_mouvemente', 'est_prototype',
            'operations', 'reservations', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'date_debut_planifiee', 'date_fin_planifiee',
            'stock_mouvemente', 'created_at', 'updated_at',
        ]


class CoutStandardSerializer(serializers.ModelSerializer):
    cout_unitaire_total = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CoutStandard
        fields = [
            'id', 'produit', 'version', 'cout_matiere', 'cout_main_oeuvre',
            'cout_indirect_pct', 'date_effective', 'cout_unitaire_total',
            'created_at',
        ]
        read_only_fields = [
            'id', 'version', 'cout_matiere', 'cout_main_oeuvre',
            'cout_unitaire_total', 'created_at',
        ]


class OrdreModificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrdreModification
        fields = [
            'id', 'produit', 'type_eco', 'description', 'statut',
            'date_effectivite', 'changements', 'demandeur', 'approbateur',
            'applique_le', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'statut', 'demandeur', 'approbateur', 'applique_le',
            'created_at', 'updated_at',
        ]
