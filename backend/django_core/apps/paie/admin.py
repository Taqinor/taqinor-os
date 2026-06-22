from django.contrib import admin

from .models import BaremeIR, ParametrePaie, Rubrique, TrancheIR


@admin.register(ParametrePaie)
class ParametrePaieAdmin(admin.ModelAdmin):
    list_display = ('id', 'date_effet', 'smig', 'smag', 'plafond_cnss',
                    'company', 'actif', 'valide_par_fondateur')
    list_filter = ('actif', 'valide_par_fondateur')
    search_fields = ('company__nom',)


class TrancheIRInline(admin.TabularInline):
    model = TrancheIR
    extra = 0
    fields = ('ordre', 'borne_min', 'borne_max', 'taux', 'somme_a_deduire')


@admin.register(BaremeIR)
class BaremeIRAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'date_effet', 'company', 'actif',
                    'valide_par_fondateur')
    list_filter = ('actif', 'valide_par_fondateur')
    search_fields = ('libelle',)
    inlines = [TrancheIRInline]


@admin.register(TrancheIR)
class TrancheIRAdmin(admin.ModelAdmin):
    list_display = ('id', 'bareme', 'ordre', 'borne_min', 'borne_max', 'taux',
                    'somme_a_deduire', 'company')
    list_filter = ('bareme',)
    search_fields = ('bareme__libelle',)


@admin.register(Rubrique)
class RubriqueAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'libelle', 'type', 'imposable',
                    'soumis_cnss', 'soumis_amo', 'soumis_cimr', 'compte',
                    'ordre', 'actif', 'company')
    list_filter = ('type', 'imposable', 'soumis_cnss', 'soumis_amo',
                   'soumis_cimr', 'actif')
    search_fields = ('code', 'libelle')
