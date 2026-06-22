from django.contrib import admin

from .models import Projet, ProjetActivity, ProjetChantier, ProjetLien


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


@admin.register(ProjetActivity)
class ProjetActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'projet', 'old_value', 'new_value', 'auteur',
                    'company', 'date_creation')
    list_filter = ('company',)
    search_fields = ('old_value', 'new_value')
