from django.contrib import admin

from .models import (
    Departement,
    DocumentEmploye,
    DossierEmploye,
    Remuneration,
)


@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ('nom', 'code', 'company', 'actif')
    list_filter = ('actif',)
    search_fields = ('nom', 'code')


@admin.register(Remuneration)
class RemunerationAdmin(admin.ModelAdmin):
    list_display = ('employe', 'montant', 'devise', 'periodicite',
                    'date_effet', 'company')
    list_filter = ('periodicite', 'devise')
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom')


@admin.register(DossierEmploye)
class DossierEmployeAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'nom', 'prenom', 'poste', 'departement',
                    'type_contrat', 'contrat_date_fin', 'statut', 'company')
    list_filter = ('type_contrat', 'statut', 'departement')
    search_fields = ('matricule', 'nom', 'prenom', 'cin', 'email')


@admin.register(DocumentEmploye)
class DocumentEmployeAdmin(admin.ModelAdmin):
    list_display = ('employe', 'type_document', 'date_expiration',
                    'date_creation', 'company')
    list_filter = ('type_document',)
    search_fields = ('employe__matricule', 'employe__nom', 'employe__prenom')
