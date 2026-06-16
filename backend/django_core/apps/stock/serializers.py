from rest_framework import serializers
from .models import Produit, Categorie, Fournisseur, MouvementStock, Marque
from apps.customfields.mixins import CustomFieldsSerializerMixin


class CategorieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categorie
        fields = '__all__'


class MarqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marque
        # company posée côté serveur (perform_create) — jamais du corps.
        fields = ['id', 'nom']

    def validate_nom(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Nom requis.')
        return value


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
        # company is force-assigned in perform_create — never accept it from the body.
        read_only_fields = [
            'quantite_avant', 'quantite_apres', 'created_by', 'date', 'company',
        ]


class ProduitSerializer(CustomFieldsSerializerMixin, serializers.ModelSerializer):
    custom_fields_module = 'produit'
    categorie = CategorieSerializer(read_only=True)
    categorie_id = serializers.PrimaryKeyRelatedField(
        queryset=Categorie.objects.none(),
        source='categorie',
        write_only=True,
        required=False,
        allow_null=True,
    )
    fournisseur = FournisseurSerializer(read_only=True)
    fournisseur_id = serializers.PrimaryKeyRelatedField(
        queryset=Fournisseur.objects.none(),
        source='fournisseur',
        write_only=True,
        required=False,
        allow_null=True,
    )

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request and hasattr(request.user, 'company_id') and request.user.company_id:
            company = request.user.company
            fields['categorie_id'].queryset = Categorie.objects.filter(company=company)
            fields['fournisseur_id'].queryset = Fournisseur.objects.filter(company=company)
        elif request and request.user.is_superuser:
            fields['categorie_id'].queryset = Categorie.objects.all()
            fields['fournisseur_id'].queryset = Fournisseur.objects.all()
        return fields
    is_low_stock = serializers.SerializerMethodField()
    nb_mouvements = serializers.SerializerMethodField()
    premiere_date_mouvement = serializers.SerializerMethodField()
    derniere_date_mouvement = serializers.SerializerMethodField()
    # Nom de la marque liée (lecture). Le texte libre `marque` reste exposé tel
    # quel (additif) ; ce champ reflète le FK quand il existe.
    marque_ref_nom = serializers.CharField(
        source='marque_ref.nom', read_only=True, default=None)

    class Meta:
        model = Produit
        fields = '__all__'

    def _resolve_marque(self, validated_data):
        """Crée/relie la marque (create-on-type) à partir du texte `marque`.

        ADDITIF : le texte `marque` reste enregistré tel quel ; on remplit en
        plus le FK `marque_ref` (jamais on ne supprime le texte). Scopé société.
        """
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None or 'marque' not in validated_data:
            return
        nom = (validated_data.get('marque') or '').strip()
        if not nom:
            validated_data['marque_ref'] = None
            return
        marque, _ = Marque.objects.get_or_create(company=company, nom=nom)
        validated_data['marque_ref'] = marque

    def create(self, validated_data):
        self._resolve_marque(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._resolve_marque(validated_data)
        return super().update(instance, validated_data)

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
