from django.contrib import admin

from .models import IdentityProvider


@admin.register(IdentityProvider)
class IdentityProviderAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'protocol', 'nom', 'actif', 'enforce_sso')
    list_filter = ('protocol', 'actif', 'enforce_sso')
    search_fields = ('nom', 'entity_id')
