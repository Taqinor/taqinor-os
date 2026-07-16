from django.contrib import admin

from .models import IpAllowRule, NetworkPolicy


class IpAllowRuleInline(admin.TabularInline):
    model = IpAllowRule
    extra = 0
    fields = ('cidr', 'label')


@admin.register(NetworkPolicy)
class NetworkPolicyAdmin(admin.ModelAdmin):
    list_display = ('company', 'mode', 'applies_to', 'updated_at')
    list_filter = ('mode', 'applies_to')
    inlines = [IpAllowRuleInline]


@admin.register(IpAllowRule)
class IpAllowRuleAdmin(admin.ModelAdmin):
    list_display = ('cidr', 'label', 'policy', 'company')
    search_fields = ('cidr', 'label')
