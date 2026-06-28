from django.contrib import admin

from .models import (
    ActionCorrectivePreventive, NonConformite, PlanInspectionChantier,
    PlanInspectionModele, PointControleModele, ProcedureQualite,
    ReleveControle, ReleveCourbeIV,
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


@admin.register(PlanInspectionChantier)
class PlanInspectionChantierAdmin(admin.ModelAdmin):
    list_display = ('id', 'modele', 'chantier_id', 'statut',
                    'date_ouverture', 'company', 'date_creation')
    list_filter = ('statut',)
    search_fields = ('modele__nom', 'modele__code')


@admin.register(ReleveControle)
class ReleveControleAdmin(admin.ModelAdmin):
    list_display = ('id', 'plan_chantier', 'point', 'conforme',
                    'date_releve', 'releve_par', 'company')
    list_filter = ('conforme',)
    search_fields = ('valeur', 'point__intitule')


@admin.register(ReleveCourbeIV)
class ReleveCourbeIVAdmin(admin.ModelAdmin):
    list_display = ('id', 'string_id', 'chantier_id', 'voc', 'isc',
                    'pmpp', 'date_releve', 'releve_par', 'company')
    search_fields = ('string_id', 'notes')


@admin.register(ProcedureQualite)
class ProcedureQualiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'reference', 'titre', 'version', 'statut',
                    'date_application', 'auteur', 'company', 'date_creation')
    list_filter = ('statut',)
    search_fields = ('reference', 'titre', 'contenu')
