from django.contrib import admin

from .models import (
    ActionCorrectivePreventive, NonConformite, PlanInspectionModele,
    PointControleModele,
)


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


@admin.register(PlanInspectionModele)
class PlanInspectionModeleAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'nom', 'actif', 'company', 'date_creation')
    list_filter = ('actif',)
    search_fields = ('code', 'nom', 'description')


@admin.register(PointControleModele)
class PointControleModeleAdmin(admin.ModelAdmin):
    list_display = ('id', 'plan', 'ordre', 'intitule', 'phase',
                    'type_releve', 'hold_point', 'company')
    list_filter = ('type_releve', 'hold_point')
    search_fields = ('intitule', 'phase', 'description')
