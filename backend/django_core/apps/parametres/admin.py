from django.contrib import admin

from .models import CompanyProfile


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    """NTADM7 — panneau founder pour assigner un palier de licence
    (``plan``) à une société. Édition RÉSERVÉE au founder (superuser Django) :
    jamais un écran tenant-facing (le tenant voit son profil en lecture via
    ``GET /parametres/profile/``, plan y compris — jamais en écriture)."""

    list_display = ('nom', 'company', 'plan', 'nb_sieges_max')
    list_filter = ('plan',)
    search_fields = ('nom',)
