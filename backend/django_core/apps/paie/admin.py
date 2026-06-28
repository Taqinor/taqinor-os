from django.contrib import admin

from .models import (
    BaremeIR,
    ElementVariable,
    ParametrePaie,
    PeriodePaie,
    ProfilPaie,
    Rubrique,
    RubriqueEmploye,
    TrancheIR,
)


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
                    'soumis_cnss', 'soumis_amo', 'soumis_cimr',
                    'avantage_nature', 'plafond_exoneration', 'compte',
                    'ordre', 'actif', 'company')
    list_filter = ('type', 'imposable', 'soumis_cnss', 'soumis_amo',
                   'soumis_cimr', 'avantage_nature', 'actif')
    search_fields = ('code', 'libelle')


@admin.register(ProfilPaie)
class ProfilPaieAdmin(admin.ModelAdmin):
    list_display = ('id', 'employe', 'type_remuneration', 'salaire_base',
                    'jours_travail_mensuel', 'heures_travail_mensuel',
                    'affilie_cnss', 'affilie_amo', 'affilie_cimr',
                    'actif', 'company')
    list_filter = ('type_remuneration', 'affilie_cnss', 'affilie_amo',
                   'affilie_cimr', 'actif')
    search_fields = ('employe__nom', 'employe__prenom', 'employe__matricule')


@admin.register(RubriqueEmploye)
class RubriqueEmployeAdmin(admin.ModelAdmin):
    list_display = ('id', 'profil', 'rubrique', 'montant', 'taux', 'actif',
                    'company')
    list_filter = ('actif',)
    search_fields = ('rubrique__code', 'rubrique__libelle')


@admin.register(PeriodePaie)
class PeriodePaieAdmin(admin.ModelAdmin):
    list_display = ('id', 'annee', 'mois', 'statut', 'date_paiement',
                    'date_cloture', 'company')
    list_filter = ('statut', 'annee')


@admin.register(ElementVariable)
class ElementVariableAdmin(admin.ModelAdmin):
    list_display = ('id', 'periode', 'profil', 'type', 'rubrique', 'quantite',
                    'montant', 'source', 'company')
    list_filter = ('type', 'source')
    search_fields = ('libelle',)
