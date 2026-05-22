from django.contrib import admin
from .models import Produit, Categorie, Fournisseur, MouvementStock


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')
    search_fields = ('nom',)


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ('nom', 'email', 'telephone')
    search_fields = ('nom', 'email')


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ('nom', 'sku', 'prix_vente', 'quantite_stock', 'categorie', 'fournisseur')
    list_filter = ('categorie', 'fournisseur')
    search_fields = ('nom', 'sku')
    raw_id_fields = ('categorie', 'fournisseur')


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = ('produit', 'type_mouvement', 'quantite', 'quantite_avant', 'quantite_apres', 'date')
    list_filter = ('type_mouvement',)
    search_fields = ('produit__nom', 'reference')
    readonly_fields = ('quantite_avant', 'quantite_apres', 'date')
