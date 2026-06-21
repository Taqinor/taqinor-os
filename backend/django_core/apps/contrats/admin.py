from django.contrib import admin

from .models import Contrat


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'objet', 'type_contrat', 'statut',
                    'montant', 'devise', 'company')
    list_filter = ('type_contrat', 'statut')
    search_fields = ('reference', 'objet')
