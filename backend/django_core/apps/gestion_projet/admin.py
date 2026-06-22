from django.contrib import admin

from .models import (
    DependanceTache,
    Jalon,
    PhaseProjet,
    Projet,
    ProjetActivity,
    ProjetChantier,
    ProjetLien,
    Tache,
)


@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ('code', 'nom', 'statut', 'company', 'responsable',
                    'date_debut', 'date_fin_prevue')
    list_filter = ('statut',)
    search_fields = ('code', 'nom', 'description')


@admin.register(ProjetChantier)
class ProjetChantierAdmin(admin.ModelAdmin):
    list_display = ('id', 'projet', 'chantier_id', 'libelle', 'company')
    list_filter = ('company',)
    search_fields = ('libelle',)


@admin.register(ProjetLien)
class ProjetLienAdmin(admin.ModelAdmin):
    list_display = ('id', 'projet', 'type_cible', 'cible_id', 'libelle',
                    'company')
    list_filter = ('type_cible', 'company')
    search_fields = ('libelle',)


@admin.register(PhaseProjet)
class PhaseProjetAdmin(admin.ModelAdmin):
    list_display = ('id', 'projet', 'type_phase', 'ordre', 'statut',
                    'avancement_pct', 'company')
    list_filter = ('type_phase', 'statut', 'company')
    search_fields = ('libelle',)


@admin.register(Tache)
class TacheAdmin(admin.ModelAdmin):
    list_display = ('id', 'code_wbs', 'libelle', 'projet', 'phase', 'parent',
                    'statut', 'avancement_pct', 'company')
    list_filter = ('statut', 'company')
    search_fields = ('libelle', 'code_wbs')


@admin.register(DependanceTache)
class DependanceTacheAdmin(admin.ModelAdmin):
    list_display = ('id', 'predecesseur', 'successeur', 'type_dependance',
                    'lag', 'company')
    list_filter = ('type_dependance', 'company')


@admin.register(Jalon)
class JalonAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'projet', 'date_prevue', 'date_reelle',
                    'statut', 'facturation_pct', 'company')
    list_filter = ('statut', 'company')
    search_fields = ('libelle', 'description')


@admin.register(ProjetActivity)
class ProjetActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'projet', 'old_value', 'new_value', 'auteur',
                    'company', 'date_creation')
    list_filter = ('company',)
    search_fields = ('old_value', 'new_value')
