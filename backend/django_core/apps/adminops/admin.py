from django.contrib import admin

from .models import PlanLicence


@admin.register(PlanLicence)
class PlanLicenceAdmin(admin.ModelAdmin):
    """NTADM7 — catalogue des paliers de licence. Édition RÉSERVÉE au
    founder (seul superuser Django accède à cet admin) — jamais un écran
    tenant-facing."""

    list_display = ('code', 'nom', 'actif', 'modules_inclus')
    list_filter = ('actif',)
    search_fields = ('code', 'nom')
