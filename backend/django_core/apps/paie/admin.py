from django.contrib import admin

from core.admin_scoping import CompanyScopedAdminMixin

from .models import (
    BaremeIR,
    BulletinPaie,
    ElementVariable,
    LigneBulletin,
    ParametrePaie,
    PeriodePaie,
    ProfilPaie,
    Rubrique,
    RubriqueEmploye,
    TrancheIR,
)


# ── AUD417 — scope société de TOUTE l'administration de ce module ───────────
# Extension du mixin AUD185 (`core/admin_scoping.py`), déjà appliqué à
# ventes/compta : aucun `ModelAdmin` de ce fichier ne bornait sa liste à
# `request.user.company`, alors que ses modèles portent un FK `company`. Un
# superutilisateur RATTACHÉ À UNE SOCIÉTÉ y voyait — et cherchait par nom —
# les lignes de TOUTES les sociétés clientes simultanément. Le mixin est
# défensif : modèle sans FK `company`, ou compte sans société (opérateur
# plateforme), ⇒ aucun filtre, comportement historique inchangé.
class CompanyScopedAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    """`ModelAdmin` dont la liste est bornée à `request.user.company`."""


# ── AUD721 — l'immuabilité du bulletin validé s'arrêtait à la porte de /admin/
# `BulletinPaie.save`/`delete` et `LigneBulletin.save`/`delete` lèvent
# `BulletinVerrouille` — mais UNIQUEMENT sur un `instance.delete()` Python.
# L'action groupée « Supprimer les objets sélectionnés » du Django admin
# exécute un DELETE SQL EN MASSE qui n'invoque JAMAIS ces surcharges : un
# bulletin déjà validé (pièce comptable et sociale) partait sans un bruit. Et
# `ProfilPaie`/`PeriodePaie` n'avaient aucune garde alors que `BulletinPaie`
# cascadait sur les deux (corrigé en PROTECT dans le même lot).
class NoBulkDeleteAdmin(CompanyScopedAdmin):
    """`ModelAdmin` sans action groupée de suppression.

    Retire `delete_selected` : la suppression reste possible OBJET PAR OBJET
    (ce qui passe, elle, par `Model.delete()` et donc par les gardes
    d'immuabilité), jamais par un DELETE SQL en masse qui les contourne.
    """

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions


@admin.register(ParametrePaie)
class ParametrePaieAdmin(CompanyScopedAdmin):
    list_display = ('id', 'date_effet', 'smig', 'smag', 'plafond_cnss',
                    'company', 'actif', 'valide_par_fondateur')
    list_filter = ('actif', 'valide_par_fondateur')
    search_fields = ('company__nom',)


class TrancheIRInline(admin.TabularInline):
    model = TrancheIR
    extra = 0
    fields = ('ordre', 'borne_min', 'borne_max', 'taux', 'somme_a_deduire')


@admin.register(BaremeIR)
class BaremeIRAdmin(CompanyScopedAdmin):
    list_display = ('id', 'libelle', 'date_effet', 'company', 'actif',
                    'valide_par_fondateur')
    list_filter = ('actif', 'valide_par_fondateur')
    search_fields = ('libelle',)
    inlines = [TrancheIRInline]


@admin.register(TrancheIR)
class TrancheIRAdmin(CompanyScopedAdmin):
    list_display = ('id', 'bareme', 'ordre', 'borne_min', 'borne_max', 'taux',
                    'somme_a_deduire', 'company')
    list_filter = ('bareme',)
    search_fields = ('bareme__libelle',)


@admin.register(Rubrique)
class RubriqueAdmin(CompanyScopedAdmin):
    list_display = ('id', 'code', 'libelle', 'type', 'imposable',
                    'soumis_cnss', 'soumis_amo', 'soumis_cimr',
                    'avantage_nature', 'plafond_exoneration', 'compte',
                    'ordre', 'actif', 'company')
    list_filter = ('type', 'imposable', 'soumis_cnss', 'soumis_amo',
                   'soumis_cimr', 'avantage_nature', 'actif')
    search_fields = ('code', 'libelle')


@admin.register(ProfilPaie)
class ProfilPaieAdmin(NoBulkDeleteAdmin):
    list_display = ('id', 'employe', 'type_remuneration', 'salaire_base',
                    'jours_travail_mensuel', 'heures_travail_mensuel',
                    'affilie_cnss', 'affilie_amo', 'affilie_cimr',
                    'actif', 'company')
    list_filter = ('type_remuneration', 'affilie_cnss', 'affilie_amo',
                   'affilie_cimr', 'actif')
    search_fields = ('employe__nom', 'employe__prenom', 'employe__matricule')

    def has_delete_permission(self, request, obj=None):
        """AUD721 — un profil PORTEUR de bulletins ne se supprime pas.

        La FK est désormais en PROTECT côté base ; on le dit ici au lieu de
        laisser l'admin proposer un bouton qui finirait en ProtectedError.
        """
        if obj is not None and obj.bulletins.exists():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(RubriqueEmploye)
class RubriqueEmployeAdmin(CompanyScopedAdmin):
    list_display = ('id', 'profil', 'rubrique', 'montant', 'taux', 'actif',
                    'company')
    list_filter = ('actif',)
    search_fields = ('rubrique__code', 'rubrique__libelle')


@admin.register(PeriodePaie)
class PeriodePaieAdmin(NoBulkDeleteAdmin):
    list_display = ('id', 'annee', 'mois', 'statut', 'date_paiement',
                    'date_cloture', 'company')
    list_filter = ('statut', 'annee')

    def has_delete_permission(self, request, obj=None):
        """AUD721 — une période PORTEUSE de bulletins ne se supprime pas."""
        if obj is not None and obj.bulletins.exists():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(ElementVariable)
class ElementVariableAdmin(CompanyScopedAdmin):
    list_display = ('id', 'periode', 'profil', 'type', 'rubrique', 'quantite',
                    'montant', 'source', 'company')
    list_filter = ('type', 'source')
    search_fields = ('libelle',)


class LigneBulletinInline(admin.TabularInline):
    model = LigneBulletin
    extra = 0
    fields = ('ordre', 'code', 'libelle', 'type', 'montant')


@admin.register(BulletinPaie)
class BulletinPaieAdmin(NoBulkDeleteAdmin):
    list_display = ('id', 'periode', 'profil', 'statut', 'brut', 'net_a_payer',
                    'date_validation', 'company')
    list_filter = ('statut',)
    search_fields = ('profil__employe__nom', 'profil__employe__prenom')
    inlines = [LigneBulletinInline]

    def has_delete_permission(self, request, obj=None):
        """AUD721 — un bulletin VALIDÉ est figé, jusque dans /admin/."""
        if obj is not None and obj.est_valide:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(LigneBulletin)
class LigneBulletinAdmin(NoBulkDeleteAdmin):
    list_display = ('id', 'bulletin', 'ordre', 'code', 'libelle', 'type',
                    'montant', 'company')
    list_filter = ('type',)
    search_fields = ('code', 'libelle')

    def has_delete_permission(self, request, obj=None):
        """AUD721 — les lignes d'un bulletin VALIDÉ sont gelées."""
        if obj is not None and obj.bulletin_id and obj.bulletin.est_valide:
            return False
        return super().has_delete_permission(request, obj)
