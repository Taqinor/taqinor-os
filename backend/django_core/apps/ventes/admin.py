from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError

from core.admin_scoping import CompanyScopedAdminMixin

from .models import Devis, LigneDevis, BonCommande, Facture, LigneFacture


class LigneDevisInline(admin.TabularInline):
    model = LigneDevis
    extra = 1


class LigneFactureInline(admin.TabularInline):
    model = LigneFacture
    extra = 1


@admin.register(Devis)
class DevisAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ('reference', 'client', 'statut', 'date_creation', 'date_validite')
    list_filter = ('statut',)
    search_fields = ('reference', 'client__nom')
    readonly_fields = ('reference', 'date_creation', 'fichier_pdf')
    inlines = [LigneDevisInline]


@admin.register(BonCommande)
class BonCommandeAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ('reference', 'client', 'statut', 'date_creation', 'date_livraison_prevue')
    list_filter = ('statut',)
    search_fields = ('reference', 'client__nom')
    readonly_fields = ('reference', 'date_creation')


# ── AUD185 (F3) — l'administration Django n'est plus une porte dérobée ──────
# Le verrou de période comptable (YLEDG3) et le gel des champs financiers
# (XFAC24) vivaient EXCLUSIVEMENT dans `FactureViewSet`
# (apps/ventes/views/facture.py) ; `Facture.save()` (apps/facturation/models.py)
# n'en porte aucun. Un superutilisateur ouvrant /admin/ pouvait donc réécrire
# `remise_globale`, `taux_tva`, `escompte_*` ou `type_facture` d'une facture
# ÉMISE — y compris dans un exercice clôturé — sans qu'aucun garde ne parle.
SUPPRESSION_FACTURE_POSTEE_INTERDITE = (
    "Suppression refusée : cette facture n'est plus au brouillon. Un document "
    "d'argent émis, payé ou annulé fait partie de la piste d'audit (et porte "
    "des encaissements en CASCADE) — corrigez-le par un avoir puis une "
    "nouvelle facture, jamais en le supprimant."
)


class FactureAdminForm(forms.ModelForm):
    """Rejoue le garde de période comptable (YLEDG3/FG115) sur le formulaire
    d'administration, qui n'appelait aucun service.

    `self.instance` porte encore la société et la date d'émission lues en base
    à ce stade (`clean()` s'exécute avant `_post_clean`), et `date_emission`
    est de toute façon `auto_now_add` (non éditable) : le garde évalue donc
    bien la période RÉELLE du document.
    """

    class Meta:
        model = Facture
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk:
            return cleaned
        try:
            from apps.compta.services import verifier_facture_modifiable
        except Exception:  # noqa: BLE001 — app compta absente = garde muette
            return cleaned
        try:
            verifier_facture_modifiable(self.instance)
        except DjangoValidationError as exc:
            raise forms.ValidationError(
                list(exc.messages) if exc.messages else [str(exc)])
        return cleaned


@admin.register(Facture)
class FactureAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    form = FactureAdminForm
    list_display = ('reference', 'client', 'statut', 'date_emission', 'date_echeance')
    list_filter = ('statut',)
    search_fields = ('reference', 'client__nom')
    readonly_fields = ('reference', 'date_emission', 'fichier_pdf')
    inlines = [LigneFactureInline]

    def get_readonly_fields(self, request, obj=None):
        """Gèle les champs FINANCIERS dès que la facture n'est plus brouillon.

        Même liste que `FACTURE_CHAMPS_FINANCIERS` (XFAC24), importée depuis le
        ViewSet pour qu'aucune divergence ne s'installe entre les deux
        surfaces. `statut` reste volontairement modifiable : l'API l'autorise
        également (bascule PAYEE), et l'adjudication de l'audit a retiré cette
        branche du périmètre.
        """
        champs = tuple(super().get_readonly_fields(request, obj))
        if obj is None or obj.statut == Facture.Statut.BROUILLON:
            return champs
        from .views.facture import FACTURE_CHAMPS_FINANCIERS
        geles = tuple(sorted(FACTURE_CHAMPS_FINANCIERS))
        return champs + tuple(c for c in geles if c not in champs)

    # ── Garde anti-suppression d'un document posté (voir le message ci-dessus)
    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.statut != Facture.Statut.BROUILLON:
            return False
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj):
        """Refus dur, même si appelé depuis une action maison."""
        if obj.statut != Facture.Statut.BROUILLON:
            raise PermissionDenied(SUPPRESSION_FACTURE_POSTEE_INTERDITE)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Idem pour la suppression en masse (`delete_selected`)."""
        if queryset.exclude(statut=Facture.Statut.BROUILLON).exists():
            raise PermissionDenied(SUPPRESSION_FACTURE_POSTEE_INTERDITE)
        super().delete_queryset(request, queryset)
