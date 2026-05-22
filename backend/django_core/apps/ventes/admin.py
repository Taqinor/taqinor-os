from django.contrib import admin
from .models import Devis, LigneDevis, BonCommande, Facture, LigneFacture


class LigneDevisInline(admin.TabularInline):
    model = LigneDevis
    extra = 1


class LigneFactureInline(admin.TabularInline):
    model = LigneFacture
    extra = 1


@admin.register(Devis)
class DevisAdmin(admin.ModelAdmin):
    list_display = ('reference', 'client', 'statut', 'date_creation', 'date_validite')
    list_filter = ('statut',)
    search_fields = ('reference', 'client__nom')
    readonly_fields = ('reference', 'date_creation', 'fichier_pdf')
    inlines = [LigneDevisInline]


@admin.register(BonCommande)
class BonCommandeAdmin(admin.ModelAdmin):
    list_display = ('reference', 'client', 'statut', 'date_creation', 'date_livraison_prevue')
    list_filter = ('statut',)
    search_fields = ('reference', 'client__nom')
    readonly_fields = ('reference', 'date_creation')


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ('reference', 'client', 'statut', 'date_emission', 'date_echeance')
    list_filter = ('statut',)
    search_fields = ('reference', 'client__nom')
    readonly_fields = ('reference', 'date_emission', 'fichier_pdf')
    inlines = [LigneFactureInline]
