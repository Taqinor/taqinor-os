"""NTOBS1/NTOBS2 — administration Django pour la rédaction manuelle des
incidents publics (le fondateur rédige TOUJOURS le récit à la main — jamais un
texte généré depuis ``core.health``, cf. ``models.py``)."""
from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin

from .models import ComponentStatus, IncidentPublic, IncidentUpdate


class CompanyScopedAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    """Un opérateur plateforme (``company`` NULL) voit tout ; un compte
    société-scopé ne voit que SES lignes (jamais les incidents système)."""


class IncidentUpdateInline(admin.TabularInline):
    model = IncidentUpdate
    extra = 1
    fields = ('statut', 'message', 'horodatage')


@admin.register(ComponentStatus)
class ComponentStatusAdmin(CompanyScopedAdmin):
    list_display = ('nom', 'region', 'statut', 'derniere_verification', 'company')
    list_filter = ('statut', 'region')
    search_fields = ('nom', 'region')


@admin.register(IncidentPublic)
class IncidentPublicAdmin(CompanyScopedAdmin):
    list_display = (
        'titre', 'severite', 'statut', 'region', 'debute_le', 'resolu_le',
        'postmortem_publie_le', 'company',
    )
    list_filter = ('severite', 'statut', 'region')
    search_fields = ('titre',)
    filter_horizontal = ('composants',)
    inlines = [IncidentUpdateInline]
    readonly_fields = ('postmortem_publie_le',)
