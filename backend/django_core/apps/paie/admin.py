from django.contrib import admin

from .models import BaremeIR, ParametrePaie, TrancheIR


@admin.register(ParametrePaie)
class ParametrePaieAdmin(admin.ModelAdmin):
    list_display = ('id', 'date_effet', 'smig', 'smag', 'plafond_cnss',
                    'company', 'actif')
    list_filter = ('actif',)
    search_fields = ('company__nom',)


class TrancheIRInline(admin.TabularInline):
    model = TrancheIR
    extra = 0
    fields = ('ordre', 'borne_min', 'borne_max', 'taux', 'somme_a_deduire')


@admin.register(BaremeIR)
class BaremeIRAdmin(admin.ModelAdmin):
    list_display = ('id', 'libelle', 'date_effet', 'company', 'actif')
    list_filter = ('actif',)
    search_fields = ('libelle',)
    inlines = [TrancheIRInline]


@admin.register(TrancheIR)
class TrancheIRAdmin(admin.ModelAdmin):
    list_display = ('id', 'bareme', 'ordre', 'borne_min', 'borne_max', 'taux',
                    'somme_a_deduire', 'company')
    list_filter = ('bareme',)
    search_fields = ('bareme__libelle',)
