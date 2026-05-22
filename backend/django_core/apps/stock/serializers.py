from rest_framework import serializers
from .models import Produit, Categorie, Fournisseur, MouvementStock


class CategorieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categorie
        fields = '__all__'


class FournisseurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fournisseur
        fields = '__all__'


class MouvementStockSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True
    )

    class Meta:
        model = MouvementStock
        fields = '__all__'
        read_only_fields = [
            'quantite_avant', 'quantite_apres', 'created_by', 'date'
        ]


class ProduitSerializer(serializers.ModelSerializer):
    categorie = CategorieSerializer(read_only=True)
    categorie_id = serializers.PrimaryKeyRelatedField(
        queryset=Categorie.objects.all(),
        source='categorie',
        write_only=True,
        required=False,
        allow_null=True,
    )
    fournisseur = FournisseurSerializer(read_only=True)
    fournisseur_id = serializers.PrimaryKeyRelatedField(
        queryset=Fournisseur.objects.all(),
        source='fournisseur',
        write_only=True,
        required=False,
        allow_null=True,
    )
    is_low_stock = serializers.SerializerMethodField()
    nb_mouvements = serializers.SerializerMethodField()
    premiere_date_mouvement = serializers.SerializerMethodField()
    derniere_date_mouvement = serializers.SerializerMethodField()

    class Meta:
        model = Produit
        fields = '__all__'

    def get_is_low_stock(self, obj):
        return obj.seuil_alerte > 0 and obj.quantite_stock <= obj.seuil_alerte

    def get_nb_mouvements(self, obj):
        return getattr(obj, 'nb_mouvements', None)

    def get_premiere_date_mouvement(self, obj):
        val = getattr(obj, 'premiere_date_mouvement', None)
        return val.isoformat() if val else None

    def get_derniere_date_mouvement(self, obj):
        val = getattr(obj, 'derniere_date_mouvement', None)
        return val.isoformat() if val else None
