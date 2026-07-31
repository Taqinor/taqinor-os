from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import Client, WebsiteLeadPayload


# Message UNIQUE (français) opposé à toute tentative de suppression de client
# depuis l'administration Django. Il NOMME le chemin supporté — même patron
# que SUPPRESSION_SOCIETE_INTERDITE (authentication/admin.py) et
# SUPPRESSION_PRODUIT_INTERDITE (apps/stock/admin.py).
#
# Pourquoi ce garde existe : `crm.Client` porte, avec le catalogue produits
# (stock.Produit) et le pipeline (crm.Lead), une des DONNÉES RÉELLES de cet
# ERP. 14 FK `PROTECT` (devis, factures, installations, tickets SAV, ventes
# POS, parrainages…) bloquent déjà — bruyamment, via la page de confirmation
# standard de Django — la suppression d'un client qui a de vrais documents.
# Mais un client SANS document (« propre ») n'est retenu par AUCUNE d'elles :
# l'admin Django le supprimait alors SILENCIEUSEMENT, effaçant en cascade son
# `crm.SiteProfile` (profil énergie/toiture réutilisable, DC12) et son
# `crm.PlanCompte`, ainsi que ses fiches contact/crédit/GED/portail liées (13
# FK `CASCADE` au total) — et VIDANT (SET_NULL) le champ `client` de TOUS ses
# leads (9 FK `SET_NULL` au total, dont `crm.Lead.client`) : les leads
# survivent, mais perdent silencieusement leur rattachement client. Le
# correctif est donc un garde d'ADMIN, jamais un changement d'`on_delete`
# (convertir 13 relations `CASCADE` cross-app en `PROTECT` serait un chantier
# de migrations à part entière, hors périmètre de ce garde).
SUPPRESSION_CLIENT_INTERDITE = (
    "Suppression d'un client INTERDITE depuis l'administration Django. Un "
    "client SANS devis/facture/installation liés (les 14 liens PROTECT du "
    "catalogue métier) n'est retenu par AUCUN garde Django : sa suppression "
    "effacerait en cascade son crm.SiteProfile (profil énergie/toiture "
    "réutilisable), son crm.PlanCompte et ses fiches contact/crédit/GED/"
    "portail liées, et viderait silencieusement le champ « client » de TOUS "
    "ses leads (ils survivent, mais perdent leur rattachement). Pour un "
    "besoin réel d'effacement RGPD, utilisez « POST /api/django/crm/clients/"
    "<id>/anonymize/ » (rôle Admin, irréversible, idempotent) : il scrube "
    "nom/email/téléphone/adresse/CIN/ICE/IF/RC tout en préservant "
    "l'intégrité comptable et les liens leads/SiteProfile/PlanCompte. Pour "
    "un doublon, fusionnez les leads concernés au lieu de supprimer le "
    "client."
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'email', 'telephone', 'date_creation')
    search_fields = ('nom', 'email')

    # ── Garde anti-perte de données (voir SUPPRESSION_CLIENT_INTERDITE) ────
    # Quatre verrous redondants — même patron que CompanyAdmin/ProduitAdmin :
    # la suppression d'un client ne doit dépendre d'aucun détail
    # d'implémentation de Django.

    def has_delete_permission(self, request, obj=None):
        """Verrou 1 — aucune suppression, pour personne (superuser compris)."""
        return False

    def get_actions(self, request):
        """Verrou 2 — retire explicitement l'action groupée `delete_selected`
        (le chemin le plus dangereux : aucun repli, contrairement à
        `ClientViewSet.destroy` qui rattrape au moins `ProtectedError`)."""
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def delete_view(self, request, object_id, extra_context=None):
        """Verrou 3 — message explicite au lieu d'un « 403 Forbidden » muet,
        pour orienter vers l'anonymisation RGPD plutôt que d'inciter au
        contournement."""
        self.message_user(request, SUPPRESSION_CLIENT_INTERDITE,
                          level=messages.ERROR)
        return HttpResponseRedirect(reverse(
            'admin:%s_%s_changelist' % (self.opts.app_label,
                                        self.opts.model_name),
            current_app=self.admin_site.name,
        ))

    def delete_model(self, request, obj):
        """Verrou 4a — refus dur, même si appelé depuis une action maison."""
        raise PermissionDenied(SUPPRESSION_CLIENT_INTERDITE)

    def delete_queryset(self, request, queryset):
        """Verrou 4b — idem pour la suppression en masse."""
        raise PermissionDenied(SUPPRESSION_CLIENT_INTERDITE)


@admin.register(WebsiteLeadPayload)
class WebsiteLeadPayloadAdmin(admin.ModelAdmin):
    """QX16 — surface LECTURE SEULE : « jamais perdre un lead » (webhooks.py)
    n'était visible nulle part. Un payload mapping-failed (error non vide,
    lead=None) était un client silencieusement perdu malgré la promesse.
    Le rejeu se fait via l'endpoint CRM dédié (ParrainageViewSet-like), pas
    depuis cet admin — cette vue est un tableau de bord, jamais un chemin
    d'écriture métier."""
    list_display = ('id', 'company', 'processed', 'error', 'received_at', 'lead')
    list_filter = ('company', 'processed')
    search_fields = ('error', 'remote_addr')
    readonly_fields = (
        'company', 'payload', 'remote_addr', 'received_at', 'processed',
        'error', 'lead',
    )
    date_hierarchy = 'received_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
