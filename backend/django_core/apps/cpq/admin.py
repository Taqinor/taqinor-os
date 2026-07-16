from django.contrib import admin

from .models import (
    OptionProduit, ContrainteCompatibilite, RegleProduitCPQ,
    OffreGroupee, LigneOffreGroupee, PrixContractuel, SeuilMargeFamille,
)


@admin.register(OptionProduit)
class OptionProduitAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'produit', 'groupe_option', 'obligatoire')
    list_filter = ('company', 'obligatoire')


@admin.register(ContrainteCompatibilite)
class ContrainteCompatibiliteAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'produit_a', 'produit_b', 'type')
    list_filter = ('company', 'type')


@admin.register(RegleProduitCPQ)
class RegleProduitCPQAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'nom', 'actif', 'date_creation')
    list_filter = ('company', 'actif')


class LigneOffreGroupeeInline(admin.TabularInline):
    model = LigneOffreGroupee
    extra = 0


@admin.register(OffreGroupee)
class OffreGroupeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'nom', 'prix_total', 'actif')
    list_filter = ('company', 'actif')
    inlines = [LigneOffreGroupeeInline]


@admin.register(PrixContractuel)
class PrixContractuelAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'client', 'produit', 'prix_ht',
                    'date_debut', 'date_fin')
    list_filter = ('company',)


@admin.register(SeuilMargeFamille)
class SeuilMargeFamilleAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'categorie', 'marge_min_pct')
    list_filter = ('company',)
