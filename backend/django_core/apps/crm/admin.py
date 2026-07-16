from django.contrib import admin
from .models import Client, WebsiteLeadPayload


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'email', 'telephone', 'date_creation')
    search_fields = ('nom', 'email')


@admin.register(WebsiteLeadPayload)
class WebsiteLeadPayloadAdmin(admin.ModelAdmin):
    """QX16 — surface LECTURE SEULE : « jamais perdre un lead » (webhooks.py)
    n'était visible nulle part. Un payload mapping-failed (error non vide,
    lead=None) était un client silencieusement perdu malgré la promesse.
    Le rejeu se fait via l'endpoint CRM dédié (ParrainageViewSet-like), pas
    depuis cet admin — cette vue est un tableau de bord, jamais un chemin
    d'écriture métier."""
    list_display = ('id', 'company', 'processed', 'error', 'received_at', 'lead')
    list_filter = ('company', 'processed')
    search_fields = ('error', 'remote_addr')
    readonly_fields = (
        'company', 'payload', 'remote_addr', 'received_at', 'processed',
        'error', 'lead',
    )
    date_hierarchy = 'received_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
