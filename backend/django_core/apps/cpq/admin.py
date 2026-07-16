from django.contrib import admin

from .models import OptionProduit, ContrainteCompatibilite


@admin.register(OptionProduit)
class OptionProduitAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'produit', 'groupe_option', 'obligatoire')
    list_filter = ('company', 'obligatoire')


@admin.register(ContrainteCompatibilite)
class ContrainteCompatibiliteAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'produit_a', 'produit_b', 'type')
    list_filter = ('company', 'type')
