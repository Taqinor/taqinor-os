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

    def save_model(self, request, obj, form, change):
        """NTADM41 — au changement de ``plan`` (SEUL point d'écriture,
        founder-only), journalise (``SettingsAuditLog``) et déclenche le
        webhook sortant ``plan.changed``. Best-effort, jamais bloquant :
        l'enregistrement du profil réussit même si la notification échoue."""
        ancien_plan_id = None
        if change and obj.pk:
            ancien_plan_id = CompanyProfile.objects.filter(
                pk=obj.pk).values_list('plan_id', flat=True).first()
        super().save_model(request, obj, form, change)
        if change and ancien_plan_id != obj.plan_id:
            from .services_licence import notifier_changement_plan
            notifier_changement_plan(
                obj, ancien_plan_id=ancien_plan_id, user=request.user)
