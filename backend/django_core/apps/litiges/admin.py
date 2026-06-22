from django.contrib import admin

from .models import Reclamation, ReclamationActivity


@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = ('id', 'objet', 'type_reclamation', 'gravite', 'statut',
                    'montant_conteste', 'company', 'date_creation')
    list_filter = ('type_reclamation', 'gravite', 'statut')
    search_fields = ('reference', 'objet', 'description')


@admin.register(ReclamationActivity)
class ReclamationActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'reclamation', 'type', 'old_value', 'new_value',
                    'auteur', 'company', 'date_creation')
    list_filter = ('type',)
    search_fields = ('message',)
