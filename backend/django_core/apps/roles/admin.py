from django.contrib import admin
from .models import Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
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
