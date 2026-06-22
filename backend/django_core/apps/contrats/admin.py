from django.contrib import admin

from .models import Contrat, PartieContrat


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'objet', 'type_contrat', 'statut',
                    'montant', 'devise', 'company')
    list_filter = ('type_contrat', 'statut')
    search_fields = ('reference', 'objet')


@admin.register(PartieContrat)
class PartieContratAdmin(admin.ModelAdmin):
    list_display = ('id', 'contrat', 'type_partie', 'nom', 'email',
                    'ordre', 'company')
    list_filter = ('type_partie',)
    search_fields = ('nom', 'email')
