from django.contrib import admin

from .models import (
    ConsumedAssertion, IdentityProvider, ScimGroupMapping, ScimToken,
)


@admin.register(IdentityProvider)
class IdentityProviderAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'protocol', 'nom', 'actif', 'enforce_sso')
    list_filter = ('protocol', 'actif', 'enforce_sso')
    search_fields = ('nom', 'entity_id')


@admin.register(ConsumedAssertion)
class ConsumedAssertionAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'assertion_id', 'consumed_at', 'expire_le')
    search_fields = ('assertion_id',)


@admin.register(ScimToken)
class ScimTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'label', 'prefix', 'actif',
                    'last_used_at')
    list_filter = ('actif',)


@admin.register(ScimGroupMapping)
class ScimGroupMappingAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'scim_group_name', 'role')
    search_fields = ('scim_group_name',)
