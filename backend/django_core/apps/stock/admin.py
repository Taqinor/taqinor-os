from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import reverse

from core.admin_scoping import CompanyScopedAdminMixin

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


# Categorie n'a PAS de garde de suppression, à la différence de Produit
# ci-dessous et de Company/Client (authentication/admin.py, apps/crm/admin.py)
# — décision DÉLIBÉRÉE, pas un oubli.
#
# Categorie est un référentiel de CLASSIFICATION, légitimement réorganisé
# (fusionner deux catégories proches, en retirer une devenue inutile…) : sa
# suppression SET_NULL `Produit.categorie` sur ses produits — les LIGNES
# survivent avec toute leur donnée réelle intacte (prix d'achat, courbe de
# pompe, fiche marque/description/garantie), seule l'étiquette de rangement
# disparaît, et elle se corrige en deux clics depuis la fiche produit. Rien
# de comparable à la perte SILENCIEUSE et IRRÉVERSIBLE que gardent
# CompanyAdmin/ProduitAdmin (là, c'est la ligne elle-même qui disparaît). Un
# garde ici bloquerait un rangement légitime sans protéger de donnée réelle — « un
# garde-fou que personne ne veut est pire que pas de garde-fou du tout ».
# Verrouillé par `apps/stock/test_admin_produit_delete_guard.py::
# test_garde_cible_une_categorie_reste_supprimable` (une catégorie reste
# supprimable après l'ajout du garde Produit).
@admin.register(Categorie)
class CategorieAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ('nom', 'description')
    search_fields = ('nom',)


@admin.register(Fournisseur)
class FournisseurAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
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


# Message UNIQUE (français) opposé à VIDER (jamais à MODIFIER) `prix_achat`
# ou `courbe_pompe` depuis l'administration Django — le garde de suppression
# ci-dessus protège la LIGNE ; celui-ci protège deux CHAMPS précis dessus.
#
# Pourquoi ce garde existe : ces deux champs sont de la VRAIE donnée fournisseur
# saisie à la main (prix d'achat négocié, courbe de performance constructeur
# OSP), jamais reconstructible depuis l'ERP — et un superutilisateur ouvrant la
# fiche produit dans /admin/ pouvait la vider d'un simple « Enregistrer », sans
# le moindre avertissement (le garde de suppression ci-dessus ne couvre QUE la
# ligne, pas ses champs). Ciblé — pas un champ passé en lecture seule : changer
# `prix_achat` de 900 à 850 (le fournisseur a baissé son prix), ou corriger un
# point de la courbe, reste un `Enregistrer` normal ; seule la transition
# « valeur réelle → vide » est refusée.
#
# `stock.Produit` est dans `apps.audit.signals.TRACKED_MODELS` : TOUTE
# sauvegarde depuis /admin/ (y compris une tentative de vidage refusée par ce
# formulaire, une fois corrigée) pose déjà, automatiquement, une ligne
# `AuditLog` avec le diff structuré `changes` (ancien → nouveau) — visible
# dans `/admin/audit/auditlog/` (apps/audit/admin.py, lecture seule). Réutilisé
# ici plutôt que ré-écrit : c'est l'entonnoir d'audit du dépôt (ARC16), pas un
# mécanisme maison.
CHAMP_CATALOGUE_VIDE_INTERDIT = (
    "Vider ce champ depuis l'administration Django est INTERDIT : il porte "
    "une donnée catalogue RÉELLE saisie à la main (prix d'achat fournisseur "
    "négocié, ou courbe de performance constructeur d'une pompe OSP), non "
    "reconstructible depuis l'ERP. Remplacez-la par la NOUVELLE valeur au "
    "lieu de la vider — si elle doit réellement redevenir vide, c'est une "
    "décision fondateur, pas un simple clic « Enregistrer ». Chaque "
    "modification de ce champ (même acceptée) reste de toute façon "
    "journalisée avec l'ancienne et la nouvelle valeur : voir /admin/audit/"
    "auditlog/."
)


class ProduitAdminForm(forms.ModelForm):
    """Verrou de champ (voir CHAMP_CATALOGUE_VIDE_INTERDIT) : refuse la
    transition « prix_achat/courbe_pompe déjà renseigné → vidé » — jamais une
    autre modification de ces champs, ni la création (un produit fraîchement
    saisi, notamment une pompe OSP « prix à renseigner », part légitimement
    sans prix). `self.instance` porte encore les valeurs AVANT édition à ce
    stade (`clean()` s'exécute avant `_post_clean`/`construct_instance`), donc
    aucune requête DB supplémentaire n'est nécessaire pour comparer."""

    class Meta:
        model = Produit
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            ancien_prix = self.instance.prix_achat
            if ('prix_achat' in cleaned and ancien_prix
                    and cleaned.get('prix_achat') == 0):
                self.add_error('prix_achat', CHAMP_CATALOGUE_VIDE_INTERDIT)

            ancienne_courbe = self.instance.courbe_pompe
            if ('courbe_pompe' in cleaned and ancienne_courbe
                    and not cleaned.get('courbe_pompe')):
                self.add_error('courbe_pompe', CHAMP_CATALOGUE_VIDE_INTERDIT)
        return cleaned


@admin.register(Produit)
class ProduitAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    form = ProduitAdminForm
    list_display = ('nom', 'sku', 'prix_vente', 'quantite_stock', 'categorie', 'fournisseur')
    list_filter = ('categorie', 'fournisseur')
    search_fields = ('nom', 'sku')
    # APX18 — `photo` en raw_id : le formulaire admin est en `fields='__all__'`,
    # et un select déroulant chargerait TOUTES les pièces jointes de la base.
    raw_id_fields = ('categorie', 'fournisseur', 'photo')

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


# AUD215 — message UNIQUE (français) opposé à toute écriture sur le registre
# des mouvements de stock depuis l'administration Django.
#
# Pourquoi ce garde existe : `MouvementStock` n'est pas une table de saisie,
# c'est le REGISTRE sur lequel se reconstruit l'inventaire.
# `services._quantite_produit_a_date` remonte au dernier `quantite_apres`
# antérieur à une date, `valorisation_a_date` (XSTK13) s'appuie dessus, et
# `figer_inventaire_annuel` en tire un inventaire déclaré « immuable » (CGNC).
# L'admin ne déclarait que trois `readonly_fields` : `produit`,
# `type_mouvement`, `quantite` restaient librement éditables, et l'ajout comme
# la suppression étaient ouverts. Modifier ou supprimer UNE ligne réécrit donc
# rétroactivement la quantité reconstruite à TOUTE date postérieure — en
# silence, et sans qu'aucun mouvement ne trace la correction.
#
# Le registre passe donc en LECTURE SEULE STRICTE : une correction se fait par
# un mouvement d'AJUSTEMENT métier (qui, lui, est daté, tracé et rejoue la
# valorisation), jamais par une réécriture de l'historique. Verrous redondants
# calqués sur `ProduitAdmin`/`FournisseurAdmin` ci-dessus : la protection ne
# doit dépendre d'aucun détail d'implémentation de Django.
MOUVEMENT_STOCK_LECTURE_SEULE = (
    "Le registre des mouvements de stock est en LECTURE SEULE dans "
    "l'administration Django : ajouter, modifier ou supprimer une ligne "
    "réécrirait rétroactivement la quantité reconstruite à toute date "
    "postérieure (valorisation à date, inventaire annuel figé). Une correction "
    "passe par un mouvement d'AJUSTEMENT depuis l'écran Stock, qui est daté et "
    "tracé, jamais par une réécriture de l'historique."
)


@admin.register(MouvementStock)
class MouvementStockAdmin(CompanyScopedAdminMixin, admin.ModelAdmin):
    list_display = ('produit', 'type_mouvement', 'quantite', 'quantite_avant', 'quantite_apres', 'date')
    list_filter = ('type_mouvement',)
    search_fields = ('produit__nom', 'reference')
    readonly_fields = ('quantite_avant', 'quantite_apres', 'date')

    # ── AUD215 — registre en lecture seule (voir MOUVEMENT_STOCK_LECTURE_SEULE)

    def has_add_permission(self, request):
        """Verrou 1a — aucun ajout : un mouvement naît d'un service métier
        (`record_stock_movement`), jamais d'un formulaire d'administration qui
        ne recalculerait ni `quantite_avant`/`quantite_apres` ni le stock."""
        return False

    def has_change_permission(self, request, obj=None):
        """Verrou 1b — aucune modification : le registre est un journal."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Verrou 1c — aucune suppression, pour personne (superuser compris)."""
        return False

    def get_actions(self, request):
        """Verrou 2 — retire explicitement l'action groupée `delete_selected`.

        Django 5.1 la filtre déjà via `allowed_permissions = ('delete',)`, mais
        on ne dépend pas de ce détail de version : c'est le chemin groupé, le
        plus dangereux, qui corromprait le plus de lignes d'un coup.
        """
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def save_model(self, request, obj, form, change):
        """Verrou 3 — refus dur si une action maison tentait d'écrire."""
        raise PermissionDenied(MOUVEMENT_STOCK_LECTURE_SEULE)

    def delete_model(self, request, obj):
        """Verrou 4a — refus dur, même appelé depuis une action maison."""
        raise PermissionDenied(MOUVEMENT_STOCK_LECTURE_SEULE)

    def delete_queryset(self, request, queryset):
        """Verrou 4b — idem pour la suppression en masse."""
        raise PermissionDenied(MOUVEMENT_STOCK_LECTURE_SEULE)
