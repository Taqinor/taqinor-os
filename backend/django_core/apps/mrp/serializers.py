from rest_framework import serializers

from .models import Gamme, OperationGamme, PosteDeCharge


class PosteDeChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PosteDeCharge
        fields = [
            'id', 'code', 'nom', 'type_poste', 'capacite_heures_jour',
            'cout_horaire', 'calendrier_travail', 'actif',
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
            'id', 'nom', 'produit', 'version', 'actif', 'operations',
            'temps_total_prevu_1_unite', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_temps_total_prevu_1_unite(self, obj):
        from .services import temps_total_gamme
        return str(temps_total_gamme(obj, 1))
