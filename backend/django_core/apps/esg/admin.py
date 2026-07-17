from django.contrib import admin

from .models import (
    CatalogueIndicateurESG, ObjectifESGTrajectoire, PeriodeReportingESG,
    SnapshotESG,
)


@admin.register(PeriodeReportingESG)
class PeriodeReportingESGAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'company', 'date_debut', 'date_fin', 'statut')
    list_filter = ('statut', 'company')
    search_fields = ('libelle',)


@admin.register(SnapshotESG)
class SnapshotESGAdmin(admin.ModelAdmin):
    list_display = ('periode', 'company', 'figee_le')
    list_filter = ('company',)


@admin.register(CatalogueIndicateurESG)
class CatalogueIndicateurESGAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'pilier', 'company')
    list_filter = ('pilier', 'company')
    search_fields = ('code', 'libelle')


@admin.register(ObjectifESGTrajectoire)
class ObjectifESGTrajectoireAdmin(admin.ModelAdmin):
    list_display = (
        'indicateur_code', 'company', 'annee_reference', 'annee_cible',
        'actif')
    list_filter = ('actif', 'company')
