from django.contrib import admin

from .models import Projet, ProjetChantier


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
