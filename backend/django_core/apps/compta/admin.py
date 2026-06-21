from django.contrib import admin

from .models import (
    CompteComptable, CompteTresorerie, EcritureComptable, ExerciceComptable,
    Journal, LigneEcriture, PeriodeComptable, PlanComptable,
)


@admin.register(PlanComptable)
class PlanComptableAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'company', 'actif')
    list_filter = ('actif',)
    search_fields = ('code', 'libelle')


@admin.register(CompteComptable)
class CompteComptableAdmin(admin.ModelAdmin):
    list_display = ('numero', 'intitule', 'classe', 'company', 'est_tiers',
                    'lettrable', 'actif')
    list_filter = ('classe', 'est_tiers', 'lettrable', 'actif')
    search_fields = ('numero', 'intitule')


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'type_journal', 'company', 'actif')
    list_filter = ('type_journal', 'actif')
    search_fields = ('code', 'libelle')


class LigneEcritureInline(admin.TabularInline):
    model = LigneEcriture
    extra = 0
    fields = ('compte', 'libelle', 'debit', 'credit', 'lettrage')


@admin.register(EcritureComptable)
class EcritureComptableAdmin(admin.ModelAdmin):
    list_display = ('id', 'journal', 'date_ecriture', 'libelle', 'reference',
                    'statut', 'company')
    list_filter = ('statut', 'journal__type_journal')
    search_fields = ('libelle', 'reference')
    inlines = [LigneEcritureInline]


@admin.register(CompteTresorerie)
class CompteTresorerieAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'type_compte', 'banque', 'devise', 'company',
                    'actif')
    list_filter = ('type_compte', 'actif')
    search_fields = ('libelle', 'banque', 'rib', 'iban')


@admin.register(ExerciceComptable)
class ExerciceComptableAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'date_debut', 'date_fin', 'statut',
                    'an_reporte', 'company')
    list_filter = ('statut', 'an_reporte')
    search_fields = ('libelle',)


@admin.register(PeriodeComptable)
class PeriodeComptableAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'type_periode', 'date_debut', 'date_fin',
                    'verrouillee', 'company')
    list_filter = ('type_periode', 'verrouillee')
    search_fields = ('libelle',)
