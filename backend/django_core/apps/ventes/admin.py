from django.contrib import admin
from django.core.exceptions import PermissionDenied

from core.admin_scoping import CompanyScopedAdminMixin

from .models import Devis, LigneDevis, BonCommande, Facture, LigneFacture


def _devis_verrouille(devis):
    """ATOT52 — devis non modifiable (accepté, remplacé, refusé…) selon LE
    verdict de modifiabilité de l'API ; un devis en création n'est jamais verrouillé."""
    from .domain.modifiabilite import verdict
    return devis is not None and devis.pk is not None and not verdict(devis)['modifiable']


class LigneDevisInline(admin.TabularInline):
    model = LigneDevis
    extra = 1

    def has_add_permission(self, request, obj=None):
        return super().has_add_permission(request, obj) and not _devis_verrouille(obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and not _devis_verrouille(obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not _devis_verrouille(obj)


class LigneFactureInline(admin.TabularInline):
    model = LigneFacture
    extra = 1

    # ATOT51 — lignes d'une facture non brouillon : lecture seule (l'API
    # refuse création, modification et suppression, ATOT9/ATOT40).
    @staticmethod
    def _parent_fige(obj):
        return obj is not None and obj.statut != Facture.Statut.BROUILLON

    def has_add_permission(self, request, obj=None):
        return (not self._parent_fige(obj)
                and super().has_add_permission(request, obj))

    def has_change_permission(self, request, obj=None):
        return (not self._parent_fige(obj)
                and super().has_change_permission(request, obj))

    def has_delete_permission(self, request, obj=None):
        return (not self._parent_fige(obj)
                and super().has_delete_permission(request, obj))


@admin.register(Devis)
class DevisAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ('reference', 'client', 'statut', 'date_creation', 'date_validite')
    list_filter = ('statut',)
    search_fields = ('reference', 'client__nom')
    readonly_fields = ('reference', 'date_creation', 'fichier_pdf')
    inlines = [LigneDevisInline]

    def has_change_permission(self, request, obj=None):
        # ATOT52 — devis verrouillé : vue en lecture seule, un POST est refusé
        # (403) AVANT tout enregistrement (même ``updated_at`` ne bouge pas).
        return super().has_change_permission(request, obj) and not _devis_verrouille(obj)

    def get_readonly_fields(self, request, obj=None):
        base = tuple(super().get_readonly_fields(request, obj))
        if not _devis_verrouille(obj):
            return base
        meta = self.model._meta
        return base + tuple(f.name for f in (*meta.fields, *meta.many_to_many)
                            if f.name not in base)


@admin.register(BonCommande)
class BonCommandeAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ('reference', 'client', 'statut', 'date_creation', 'date_livraison_prevue')
    list_filter = ('statut',)
    search_fields = ('reference', 'client__nom')
    readonly_fields = ('reference', 'date_creation')

    def get_readonly_fields(self, request, obj=None):
        """ATOT51 — hors « en attente », `BC_CHAMPS_FIGES` (la liste de la
        vue, ATOT48) est en lecture seule."""
        champs = tuple(super().get_readonly_fields(request, obj))
        if obj is None or obj.statut == BonCommande.Statut.EN_ATTENTE:
            return champs
        from .views.bon_commande import BC_CHAMPS_FIGES
        return champs + tuple(c for c in BC_CHAMPS_FIGES if c not in champs)


# ── AUD185 (F3) — l'administration Django n'est plus une porte dérobée ──────
# Le gel des champs financiers (XFAC24) vivait EXCLUSIVEMENT dans
# `FactureViewSet` (apps/ventes/views/facture.py) ; `Facture.save()`
# (apps/facturation/models.py) n'en porte aucun. Un superutilisateur ouvrant
# /admin/ pouvait donc réécrire `remise_globale`, `taux_tva`, `escompte_*` ou
# `type_facture` d'une facture ÉMISE sans qu'aucun garde ne parle.
SUPPRESSION_FACTURE_POSTEE_INTERDITE = (
    "Suppression refusée : cette facture n'est plus au brouillon. Un document "
    "d'argent émis, payé ou annulé fait partie de la piste d'audit (et porte "
    "des encaissements en CASCADE) — corrigez-le par un avoir puis une "
    "nouvelle facture, jamais en le supprimant."
)


# ATOT51 — champs d'état posés par les seules actions de l'API.
ADMIN_FACTURE_ETAT = ('statut', 'abandon_motif', 'abandon_montant',
                      'abandon_date', 'abandon_auto', 'abandon_par')
# ATOT54 — identité et rattachement : posés à la création, figés hors brouillon.
ADMIN_FACTURE_IDENTITE = ('company', 'bon_commande', 'devis', 'lead',
                          'identite_vendeur', 'created_by', 'entite')


@admin.register(Facture)
class FactureAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ('reference', 'client', 'statut', 'date_emission', 'date_echeance')
    list_filter = ('statut',)
    search_fields = ('reference', 'client__nom')
    readonly_fields = ('reference', 'date_emission', 'fichier_pdf')
    inlines = [LigneFactureInline]

    def get_readonly_fields(self, request, obj=None):
        """Gèle les champs FINANCIERS dès que la facture n'est plus brouillon.

        Même liste que `FACTURE_CHAMPS_FINANCIERS` (XFAC24), importée depuis le
        ViewSet pour qu'aucune divergence ne s'installe entre les deux
        surfaces. ATOT51 — `statut` et `abandon_*` aussi : ils ne bougent que
        par les actions dédiées de l'API (paiement, annulation, abandon).
        """
        champs = tuple(super().get_readonly_fields(request, obj))
        if obj is None or obj.statut == Facture.Statut.BROUILLON:
            return champs
        from .views.facture import FACTURE_CHAMPS_FINANCIERS
        geles = tuple(sorted(FACTURE_CHAMPS_FINANCIERS)) + ADMIN_FACTURE_ETAT + ADMIN_FACTURE_IDENTITE
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
