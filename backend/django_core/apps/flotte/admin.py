from django.contrib import admin

from .models import Vehicule


@admin.register(Vehicule)
class VehiculeAdmin(admin.ModelAdmin):
    list_display = ('immatriculation', 'marque', 'modele', 'type_vehicule',
                    'energie', 'statut', 'company')
    list_filter = ('type_vehicule', 'energie', 'statut', 'company')
    search_fields = ('immatriculation', 'marque', 'modele')
