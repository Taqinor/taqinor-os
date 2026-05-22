from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('nom', 'slug', 'actif', 'nb_users', 'date_creation')
    list_filter = ('actif',)
    search_fields = ('nom', 'slug')
    readonly_fields = ('slug', 'date_creation')
    ordering = ('nom',)

    def nb_users(self, obj):
        return obj.users.count()
    nb_users.short_description = 'Utilisateurs'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            # Nouvelle entreprise : créer les 3 rôles système automatiquement
            from authentication.views import _create_system_roles
            _create_system_roles(obj)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username', 'email', 'company', 'role_display',
        'is_staff', 'is_active',
    )
    list_filter = ('role', 'company', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    autocomplete_fields = ('company',)

    fieldsets = UserAdmin.fieldsets + (
        ('Role & Entreprise', {
            'fields': (
                'role_legacy', 'role', 'company',
                'phone_number', 'address',
            )
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role & Entreprise', {
            'fields': ('role_legacy', 'role', 'company')
        }),
    )

    def role_display(self, obj):
        if obj.role:
            return obj.role.nom
        return obj.role_legacy
    role_display.short_description = 'Role'
