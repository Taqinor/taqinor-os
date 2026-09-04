from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin

from .models import IpAllowRule, NetworkPolicy


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


class IpAllowRuleInline(admin.TabularInline):
    model = IpAllowRule
    extra = 0
    fields = ('cidr', 'label')


@admin.register(NetworkPolicy)
class NetworkPolicyAdmin(CompanyScopedAdmin):
    list_display = ('company', 'mode', 'applies_to', 'updated_at')
    list_filter = ('mode', 'applies_to')
    inlines = [IpAllowRuleInline]


@admin.register(IpAllowRule)
class IpAllowRuleAdmin(CompanyScopedAdmin):
    list_display = ('cidr', 'label', 'policy', 'company')
    search_fields = ('cidr', 'label')
