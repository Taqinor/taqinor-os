from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin
from .models import Role


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


@admin.register(Role)
class RoleAdmin(CompanyScopedAdmin):
    list_display = ('nom', 'company', 'est_systeme', 'nb_permissions', 'nb_users')
    list_filter = ('est_systeme', 'company')
    search_fields = ('nom', 'company__nom')
    readonly_fields = ('est_systeme',)

    def nb_permissions(self, obj):
        return len(obj.permissions or [])
    nb_permissions.short_description = 'Permissions'

    def nb_users(self, obj):
        return obj.users.count()
    nb_users.short_description = 'Utilisateurs'
