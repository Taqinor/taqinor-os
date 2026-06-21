from django.contrib import admin

from .models import ActionCorrectivePreventive, NonConformite


@admin.register(NonConformite)
class NonConformiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'titre', 'gravite', 'statut',
                    'company', 'date_detection')
    list_filter = ('gravite', 'statut')
    search_fields = ('reference', 'titre', 'origine')


@admin.register(ActionCorrectivePreventive)
class ActionCorrectivePreventiveAdmin(admin.ModelAdmin):
    list_display = ('id', 'non_conformite', 'type_action', 'statut',
                    'responsable', 'echeance', 'company')
    list_filter = ('type_action', 'statut')
    search_fields = ('description', 'cause_racine')
