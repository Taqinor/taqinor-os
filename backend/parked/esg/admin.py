from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin

from .models import (
    CatalogueIndicateurESG, ObjectifESGTrajectoire, PeriodeReportingESG,
    SnapshotESG,
)


# ── AUD417 — scope société de TOUTE l'administration de ce module ───────────
# Extension du mixin AUD185 (`core/admin_scoping.py`), déjà appliqué à
# ventes/compta : aucun `ModelAdmin` de ce fichier ne bornait sa liste à
# `request.user.company`, alors que ses modèles portent un FK `company`. Un
# superutilisateur RATTACHÉ À UNE SOCIÉTÉ y voyait — et cherchait par nom —
# les lignes de TOUTES les sociétés clientes simultanément. Le mixin est
# défensif : modèle sans FK `company`, ou compte sans société (opérateur
# plateforme), ⇒ aucun filtre, comportement historique inchangé.
class CompanyScopedAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    """`ModelAdmin` dont la liste est bornée à `request.user.company`."""


@admin.register(PeriodeReportingESG)
class PeriodeReportingESGAdmin(CompanyScopedAdmin):
    list_display = ('libelle', 'company', 'date_debut', 'date_fin', 'statut')
    list_filter = ('statut', 'company')
    search_fields = ('libelle',)


@admin.register(SnapshotESG)
class SnapshotESGAdmin(CompanyScopedAdmin):
    list_display = ('periode', 'company', 'figee_le')
    list_filter = ('company',)


@admin.register(CatalogueIndicateurESG)
class CatalogueIndicateurESGAdmin(CompanyScopedAdmin):
    list_display = ('code', 'libelle', 'pilier', 'company')
    list_filter = ('pilier', 'company')
    search_fields = ('code', 'libelle')


@admin.register(ObjectifESGTrajectoire)
class ObjectifESGTrajectoireAdmin(CompanyScopedAdmin):
    list_display = (
        'indicateur_code', 'company', 'annee_reference', 'annee_cible',
        'actif')
    list_filter = ('actif', 'company')
