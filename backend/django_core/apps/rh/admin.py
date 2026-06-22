from django.contrib import admin

from .models import Departement, DossierEmploye


@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ('nom', 'code', 'company', 'actif')
    list_filter = ('actif',)
    search_fields = ('nom', 'code')


@admin.register(DossierEmploye)
class DossierEmployeAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'nom', 'prenom', 'poste', 'departement',
                    'type_contrat', 'contrat_date_fin', 'statut', 'company')
    list_filter = ('type_contrat', 'statut', 'departement')
    search_fields = ('matricule', 'nom', 'prenom', 'cin', 'email')
