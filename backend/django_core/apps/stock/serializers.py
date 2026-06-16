from rest_framework import serializers
from .models import (
    Produit, Categorie, Fournisseur, MouvementStock, Marque,
    BonCommandeFournisseur, LigneBonCommandeFournisseur,
)


class MarqueSerializer(serializers.ModelSerializer):
    en_usage = serializers.SerializerMethodField()

    class Meta:
        model = Marque
        fields = ['id', 'nom', 'archived', 'en_usage']

    def get_en_usage(self, obj):
        return Produit.objects.filter(company=obj.company, marque=obj.nom).count()


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
        # company is force-assigned in perform_create — never accept it from the body.
        read_only_fields = [
            'quantite_avant', 'quantite_apres', 'created_by', 'date', 'company',
        ]


class ProduitSerializer(serializers.ModelSerializer):
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


class LigneBonCommandeFournisseurSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)
    produit_sku = serializers.CharField(source='produit.sku', read_only=True)
    quantite_restante = serializers.IntegerField(read_only=True)
    total_achat = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = LigneBonCommandeFournisseur
        fields = [
            'id', 'produit', 'produit_nom', 'produit_sku', 'quantite',
            'prix_achat_unitaire', 'quantite_recue', 'quantite_restante',
            'total_achat',
        ]
        # quantite_recue n'est jamais posée librement : elle évolue uniquement
        # via l'action de réception (perform_create n'accepte que le reste).
        read_only_fields = ['quantite_recue']

    def validate_quantite(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('La quantité doit être positive.')
        return value


class BonCommandeFournisseurSerializer(serializers.ModelSerializer):
    lignes = LigneBonCommandeFournisseurSerializer(many=True)
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True)
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True)
    statut_display = serializers.CharField(
        source='get_statut_display', read_only=True)
    total_achat = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)
    est_entierement_recu = serializers.BooleanField(read_only=True)

    class Meta:
        model = BonCommandeFournisseur
        fields = [
            'id', 'reference', 'fournisseur', 'fournisseur_nom', 'statut',
            'statut_display', 'date_commande', 'note', 'created_by',
            'created_by_username', 'date_creation', 'date_mise_a_jour',
            'lignes', 'total_achat', 'est_entierement_recu',
        ]
        # company + reference + created_by sont posés côté serveur.
        read_only_fields = [
            'reference', 'created_by', 'date_creation', 'date_mise_a_jour',
        ]

    def validate_lignes(self, value):
        if not value:
            raise serializers.ValidationError('Au moins une ligne est requise.')
        return value

    def validate_fournisseur(self, value):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is not None and value.company_id != company.id:
            raise serializers.ValidationError(
                'Fournisseur hors de votre entreprise.')
        return value

    def _validate_company_produits(self, lignes_data):
        request = self.context.get('request')
        company = getattr(getattr(request, 'user', None), 'company', None)
        if company is None:
            return
        for ligne in lignes_data:
            produit = ligne['produit']
            if produit.company_id != company.id:
                raise serializers.ValidationError(
                    {'lignes': 'Produit hors de votre entreprise.'})

    def create(self, validated_data):
        lignes_data = validated_data.pop('lignes')
        self._validate_company_produits(lignes_data)
        bon = BonCommandeFournisseur.objects.create(**validated_data)
        for ligne in lignes_data:
            LigneBonCommandeFournisseur.objects.create(
                bon_commande=bon, **ligne)
        return bon

    def update(self, instance, validated_data):
        # Les écritures sur les lignes ne sont permises qu'en BROUILLON :
        # une fois envoyé/reçu, le contenu commandé est figé.
        lignes_data = validated_data.pop('lignes', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if lignes_data is not None:
            if instance.statut != BonCommandeFournisseur.Statut.BROUILLON:
                raise serializers.ValidationError(
                    'Les lignes ne sont modifiables qu\'en brouillon.')
            self._validate_company_produits(lignes_data)
            instance.lignes.all().delete()
            for ligne in lignes_data:
                LigneBonCommandeFournisseur.objects.create(
                    bon_commande=instance, **ligne)
        return instance
