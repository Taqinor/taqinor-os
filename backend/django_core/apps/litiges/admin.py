from django.contrib import admin

from .models import Reclamation


@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = ('id', 'objet', 'type_reclamation', 'gravite', 'statut',
                    'montant_conteste', 'company', 'date_creation')
    list_filter = ('type_reclamation', 'gravite', 'statut')
    search_fields = ('reference', 'objet', 'description')
