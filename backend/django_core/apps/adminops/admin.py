from django import forms
from django.contrib import admin

from .models import PlanLicence


class PlanLicenceAdminForm(forms.ModelForm):
    """APAR55 — ``modules_inclus`` validé contre les manifestes : seule une clé
    de module INSTALLABLE (celles qu'un palier peut borner) est acceptée ; une
    clé inconnue (faute de frappe) est refusée au lieu de verrouiller en
    silence le module visé."""

    class Meta:
        model = PlanLicence
        fields = '__all__'

    def clean_modules_inclus(self):
        valeur = self.cleaned_data.get('modules_inclus') or []
        if not isinstance(valeur, list) or not all(
                isinstance(cle, str) for cle in valeur):
            raise forms.ValidationError(
                'Liste de clés de module attendue, ex. ["crm", "ventes"].')
        from apps.parametres.feature_flags import modules_installables
        connues = modules_installables()
        inconnues = sorted(set(valeur) - connues)
        if inconnues:
            raise forms.ValidationError(
                'Clé(s) de module inconnue(s) : %s.' % ', '.join(inconnues))
        return valeur


@admin.register(PlanLicence)
class PlanLicenceAdmin(admin.ModelAdmin):
    """NTADM7 — catalogue des paliers de licence. Édition RÉSERVÉE au
    founder (seul superuser Django accède à cet admin) — jamais un écran
    tenant-facing."""

    form = PlanLicenceAdminForm
    list_display = ('code', 'nom', 'actif', 'modules_inclus')
    list_filter = ('actif',)
    search_fields = ('code', 'nom')

    def save_model(self, request, obj, form, change):
        """APAR55 — toute modification d'un palier est journalisée (section
        ``licence``) pour CHAQUE société qui y est rattachée (avant/après)."""
        avant = {}
        if change and obj.pk:
            avant = PlanLicence.objects.filter(pk=obj.pk).values(
                'modules_inclus', 'actif', 'nom', 'code').first() or {}
        super().save_model(request, obj, form, change)
        if change:
            from apps.parametres.services_licence import (
                journaliser_modification_palier,
            )
            journaliser_modification_palier(
                obj, avant, user=getattr(request, 'user', None))
