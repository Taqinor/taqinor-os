from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import Produit, Categorie, Fournisseur, MouvementStock


# Message UNIQUE (français) opposé à toute tentative de suppression de produit
# depuis l'administration Django. Il NOMME le chemin supporté.
#
# Pourquoi ce garde existe : le catalogue produits est de la VRAIE donnée
# saisie à la main (prix d'achat fournisseur, prix VEICHI réels, courbes de
# pompes OSP, fiches marque/description/garantie). L'API, elle, ne détruit
# JAMAIS un produit : `ProduitViewSet.destroy` rattrape `ProtectedError` et
# ARCHIVE (`is_archived = True`), l'historique est conservé. L'admin Django
# court-circuitait totalement ce repli :
#   * un produit « utilisé » (mouvements de stock, lignes de devis, factures…)
#     est protégé par les 17 FK PROTECT et refuse bruyamment — visible ;
#   * mais un produit dont les enfants restants sont tous en CASCADE (26 modèles
#     : fiches techniques, conditionnements, prix fournisseur, lots, profils
#     saisonniers…) partait SILENCIEUSEMENT, avec ses enfants — et c'est
#     exactement le cas des produits les plus coûteux à ressaisir : les pompes
#     OSP à courbe constructeur, encore sans mouvement ni devis.
# Le garde est donc INCONDITIONNEL (il ne dépend pas de la présence d'un enfant
# PROTECT), et il REFUSE au lieu de recopier l'archivage : un bouton
# « Supprimer » qui, en réalité, archive est un mensonge d'interface, et une
# divergence silencieuse entre l'admin et l'API est elle-même un défaut.
SUPPRESSION_PRODUIT_INTERDITE = (
    "Suppression d'un produit INTERDITE depuis l'administration Django : elle "
    "détruirait des données catalogue saisies à la main (prix d'achat "
    "fournisseur, courbe de pompe, fiche marque/description/garantie) ainsi "
    "que, en cascade et sans avertissement, les fiches techniques, "
    "conditionnements, prix fournisseur, lots et profils saisonniers du "
    "produit. Le chemin supporté est l'ARCHIVAGE, qui conserve tout "
    "l'historique : depuis l'écran Stock → Produits (bouton Supprimer, qui "
    "archive), ou via l'API « DELETE /api/django/stock/produits/<id>/ ». Un "
    "produit déjà archivé peut, si nécessaire, être réellement supprimé par "
    "l'action dédiée « DELETE /api/django/stock/produits/<id>/force-delete/ » "
    "(rôle Admin), qui elle passe par les garde-fous métier."
)


# Même garde, même raison, pour le FOURNISSEUR — l'autre moitié du catalogue
# réel. Un fournisseur porte les prix d'achat NÉGOCIÉS de ses références
# (`achats.PrixFournisseur`, désormais PROTECT) : sa suppression est refusée
# par le collecteur Django dès qu'un tarif existe, et l'API
# (`FournisseurViewSet.destroy`) ARCHIVE au lieu de détruire. L'admin Django
# court-circuitait ce repli exactement comme pour le produit — pire, un
# fournisseur SANS tarif mais avec contacts, documents de conformité, jetons
# portail ou profil sous-traitant partait SILENCIEUSEMENT avec eux. Le garde
# est donc INCONDITIONNEL et REFUSE (il ne recopie pas l'archivage : un bouton
# « Supprimer » qui archive est un mensonge d'interface, et une divergence
# silencieuse admin/API est elle-même un défaut).
SUPPRESSION_FOURNISSEUR_INTERDITE = (
    "Suppression d'un fournisseur INTERDITE depuis l'administration Django : "
    "elle détruirait des données catalogue saisies à la main (prix d'achat "
    "négociés par référence, paliers de quantité, code article fournisseur) "
    "ainsi que, en cascade et sans avertissement, ses contacts, documents de "
    "conformité, jetons de portail et profil sous-traitant. Le chemin "
    "supporté est l'ARCHIVAGE, qui conserve tout l'historique : depuis "
    "l'écran Stock → Fournisseurs (bouton Supprimer, qui archive), ou via "
    "l'API « DELETE /api/django/stock/fournisseurs/<id>/ ». Un fournisseur "
    "déjà archivé peut, si nécessaire, être réellement supprimé par l'action "
    "dédiée « DELETE /api/django/stock/fournisseurs/<id>/force-delete/ » "
    "(rôle Admin), qui elle refuse en 409 tant qu'un prix d'achat ou un "
    "document d'achat le retient."
)


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')
    search_fields = ('nom',)


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ('nom', 'email', 'telephone', 'is_archived')
    list_filter = ('is_archived',)
    search_fields = ('nom', 'email')

    # ── Garde anti-perte de données (voir SUPPRESSION_FOURNISSEUR_INTERDITE) ─
    # Mêmes quatre verrous redondants que `ProduitAdmin`/`CompanyAdmin` : la
    # suppression d'un fournisseur ne doit dépendre d'aucun détail
    # d'implémentation de Django.

    def has_delete_permission(self, request, obj=None):
        """Verrou 1 — aucune suppression, pour personne (superuser compris)."""
        return False

    def get_actions(self, request):
        """Verrou 2 — retire explicitement l'action groupée `delete_selected`.

        C'est le chemin le plus dangereux : il n'a AUCUN repli
        `ProtectedError` → archivage, contrairement à
        `FournisseurViewSet.destroy`.
        """
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def delete_view(self, request, object_id, extra_context=None):
        """Verrou 3 — message explicite au lieu d'un « 403 Forbidden » muet,
        pour orienter vers l'archivage plutôt que d'inciter au contournement."""
        self.message_user(request, SUPPRESSION_FOURNISSEUR_INTERDITE,
                          level=messages.ERROR)
        return HttpResponseRedirect(reverse(
            'admin:%s_%s_changelist' % (self.opts.app_label,
                                        self.opts.model_name),
            current_app=self.admin_site.name,
        ))

    def delete_model(self, request, obj):
        """Verrou 4a — refus dur, même si appelé depuis une action maison."""
        raise PermissionDenied(SUPPRESSION_FOURNISSEUR_INTERDITE)

    def delete_queryset(self, request, queryset):
        """Verrou 4b — idem pour la suppression en masse."""
        raise PermissionDenied(SUPPRESSION_FOURNISSEUR_INTERDITE)


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ('nom', 'sku', 'prix_vente', 'quantite_stock', 'categorie', 'fournisseur')
    list_filter = ('categorie', 'fournisseur')
    search_fields = ('nom', 'sku')
    raw_id_fields = ('categorie', 'fournisseur')

    # ── Garde anti-perte de données (voir SUPPRESSION_PRODUIT_INTERDITE) ────
    # Mêmes quatre verrous redondants que `CompanyAdmin` : la suppression d'un
    # produit ne doit dépendre d'aucun détail d'implémentation de Django.

    def has_delete_permission(self, request, obj=None):
        """Verrou 1 — aucune suppression, pour personne (superuser compris).

        Retire le bouton « Supprimer » de la fiche et fait échouer
        `_delete_view`/`get_deleted_objects` si l'URL est appelée directement.
        """
        return False

    def get_actions(self, request):
        """Verrou 2 — retire explicitement l'action groupée `delete_selected`.

        Sur Django 5.1 `_filter_actions_by_permissions` la retire déjà (elle
        porte `allowed_permissions = ('delete',)`), mais on ne dépend pas de ce
        détail de version : elle est retirée du dictionnaire dans tous les cas.
        C'est ce chemin groupé qui est le plus dangereux — il n'a AUCUN repli
        `ProtectedError` → archivage, contrairement à `ProduitViewSet.destroy`.
        """
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def delete_view(self, request, object_id, extra_context=None):
        """Verrou 3 — message explicite au lieu d'un « 403 Forbidden » muet,
        pour orienter vers l'archivage plutôt que d'inciter au contournement."""
        self.message_user(request, SUPPRESSION_PRODUIT_INTERDITE,
                          level=messages.ERROR)
        return HttpResponseRedirect(reverse(
            'admin:%s_%s_changelist' % (self.opts.app_label,
                                        self.opts.model_name),
            current_app=self.admin_site.name,
        ))

    def delete_model(self, request, obj):
        """Verrou 4a — refus dur, même si appelé depuis une action maison."""
        raise PermissionDenied(SUPPRESSION_PRODUIT_INTERDITE)

    def delete_queryset(self, request, queryset):
        """Verrou 4b — idem pour la suppression en masse."""
        raise PermissionDenied(SUPPRESSION_PRODUIT_INTERDITE)


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = ('produit', 'type_mouvement', 'quantite', 'quantite_avant', 'quantite_apres', 'date')
    list_filter = ('type_mouvement',)
    search_fields = ('produit__nom', 'reference')
    readonly_fields = ('quantite_avant', 'quantite_apres', 'date')
