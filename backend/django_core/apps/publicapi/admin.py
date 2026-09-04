from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin

from .models import ApiKey, Webhook, WebhookDelivery


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


@admin.register(ApiKey)
class ApiKeyAdmin(CompanyScopedAdmin):
    list_display = ('label', 'prefix', 'company', 'enabled', 'created_at',
                    'last_used_at')
    list_filter = ('enabled', 'company')
    readonly_fields = ('key_hash', 'prefix', 'created_at', 'last_used_at')


@admin.register(Webhook)
class WebhookAdmin(CompanyScopedAdmin):
    list_display = ('label', 'target_url', 'company', 'enabled', 'created_at')
    list_filter = ('enabled', 'company')
    readonly_fields = ('secret', 'created_at')


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(CompanyScopedAdmin):
    list_display = ('event', 'webhook', 'status', 'response_status',
                    'created_at')
    list_filter = ('status', 'event', 'company')
    readonly_fields = ('created_at',)
