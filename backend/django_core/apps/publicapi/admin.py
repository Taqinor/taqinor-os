from django.contrib import admin

from .models import ApiKey, Webhook, WebhookDelivery


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ('label', 'prefix', 'company', 'enabled', 'created_at',
                    'last_used_at')
    list_filter = ('enabled', 'company')
    readonly_fields = ('key_hash', 'prefix', 'created_at', 'last_used_at')


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ('label', 'target_url', 'company', 'enabled', 'created_at')
    list_filter = ('enabled', 'company')
    readonly_fields = ('secret', 'created_at')


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ('event', 'webhook', 'status', 'response_status',
                    'created_at')
    list_filter = ('status', 'event', 'company')
    readonly_fields = ('created_at',)
