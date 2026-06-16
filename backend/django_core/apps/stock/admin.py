from django.contrib import admin
from .models import (
    Produit, Categorie, Fournisseur, MouvementStock, ProduitAuditLog,
    BonCommandeFournisseur, LigneBonCommandeFournisseur,
)


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


class LigneBonCommandeFournisseurInline(admin.TabularInline):
    model = LigneBonCommandeFournisseur
    extra = 0
    raw_id_fields = ('produit',)


@admin.register(BonCommandeFournisseur)
class BonCommandeFournisseurAdmin(admin.ModelAdmin):
    list_display = ('reference', 'fournisseur', 'statut', 'date_commande',
                    'created_by', 'date_creation')
    list_filter = ('statut',)
    search_fields = ('reference', 'fournisseur__nom')
    raw_id_fields = ('fournisseur', 'created_by')
    readonly_fields = ('date_creation', 'date_mise_a_jour')
    inlines = [LigneBonCommandeFournisseurInline]


@admin.register(ProduitAuditLog)
class ProduitAuditLogAdmin(admin.ModelAdmin):
    list_display = ('produit', 'action', 'champ', 'ancienne_valeur',
                    'nouvelle_valeur', 'created_by', 'date')
    list_filter = ('action',)
    search_fields = ('produit__nom', 'champ')
    readonly_fields = ('date',)
