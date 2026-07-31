from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import CustomUser, Company


# Message UNIQUE (français) affiché/levé partout où une suppression de société
# est tentée depuis l'administration Django. Il NOMME la procédure supportée :
# le garde est une redirection vers le chemin sûr, jamais un cul-de-sac.
#
# Pourquoi ce garde existe : `stock.Produit.company` ET `crm.Lead.company` sont
# en `on_delete=CASCADE` (c'est VOULU — la purge de tenant conçue en dépend, et
# la règle YDATA3 interdit un SET_NULL sur un champ tenant). Conséquence :
# supprimer une Company depuis l'admin efface en cascade TOUT le catalogue
# produits (prix d'achat saisis à la main, courbes de pompes, fiches produit),
# TOUS les leads du pipeline commercial et les ~1 100 tables filles du tenant —
# derrière la seule page « Êtes-vous sûr ? » générique de Django, sans
# sauvegarde, sans délai de grâce, sans journal. Le correctif est donc un garde
# d'ADMIN, jamais un changement d'`on_delete`.
SUPPRESSION_SOCIETE_INTERDITE = (
    "Suppression d'une société INTERDITE depuis l'administration Django. "
    "Les champs « company » de stock.Produit et de crm.Lead sont en CASCADE : "
    "supprimer cette société effacerait irrémédiablement TOUT son catalogue "
    "produits (prix d'achat, courbes de pompes, fiches), TOUS ses leads CRM et "
    "l'intégralité de ses données liées — sans sauvegarde ni délai de grâce. "
    "Utilisez la procédure officielle de clôture/purge, qui vérifie le statut "
    "de fermeture, le délai de grâce et l'existence d'une sauvegarde terminée, "
    "et qui journalise chaque étape : "
    "« python manage.py close_company <slug> --soft-close » (fermeture "
    "réversible, données intactes), puis, une fois le délai de grâce écoulé et "
    "une sauvegarde vérifiée, « python manage.py close_company <slug> --purge » "
    "en dry-run, et enfin « --purge --yes-je-confirme » pour exécuter."
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('nom', 'slug', 'actif', 'nb_users', 'date_creation')
    list_filter = ('actif',)
    search_fields = ('nom', 'slug')
    readonly_fields = ('slug', 'date_creation')
    ordering = ('nom',)

    def nb_users(self, obj):
        return obj.users.count()
    nb_users.short_description = 'Utilisateurs'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            # Nouvelle entreprise : créer les 3 rôles système automatiquement
            from authentication.views import _create_system_roles
            _create_system_roles(obj)

    # ── Garde anti-perte de données (voir SUPPRESSION_SOCIETE_INTERDITE) ────
    # Quatre verrous, volontairement redondants : la suppression d'une société
    # est la plus grosse perte de données possible dans cet ERP, elle ne doit
    # dépendre d'aucun détail d'implémentation de Django.

    def has_delete_permission(self, request, obj=None):
        """Verrou 1 — aucune suppression, pour personne (superuser compris).

        Fait disparaître le bouton « Supprimer » de la fiche et fait échouer
        `_delete_view`/`get_deleted_objects` (PermissionDenied) si l'URL est
        appelée directement.
        """
        return False

    def get_actions(self, request):
        """Verrou 2 — retire explicitement l'action groupée `delete_selected`.

        Django 5.1 la filtre DÉJÀ via `_filter_actions_by_permissions` (elle
        porte `allowed_permissions = ('delete',)`, donc `has_delete_permission`
        ci-dessus suffit sur cette version). On ne dépend pas de ce détail :
        l'action est retirée du dictionnaire, quel que soit le comportement de
        la version de Django installée.
        """
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def delete_view(self, request, object_id, extra_context=None):
        """Verrou 3 — réponse EXPLICITE au lieu d'un 403 nu.

        `has_delete_permission = False` renverrait un « 403 Forbidden » muet,
        qui n'apprend rien à l'administrateur et l'incite à contourner le
        garde. On affiche le message français ci-dessus (qui nomme
        `close_company`) et on renvoie à la liste.
        """
        self.message_user(request, SUPPRESSION_SOCIETE_INTERDITE,
                          level=messages.ERROR)
        return HttpResponseRedirect(reverse(
            'admin:%s_%s_changelist' % (self.opts.app_label,
                                        self.opts.model_name),
            current_app=self.admin_site.name,
        ))

    def delete_model(self, request, obj):
        """Verrou 4a — même une action personnalisée qui appellerait
        directement `delete_model()` est refusée."""
        raise PermissionDenied(SUPPRESSION_SOCIETE_INTERDITE)

    def delete_queryset(self, request, queryset):
        """Verrou 4b — idem pour la suppression en masse."""
        raise PermissionDenied(SUPPRESSION_SOCIETE_INTERDITE)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'username', 'email', 'company', 'role_display',
        'is_staff', 'is_active',
    )
    list_filter = ('role', 'company', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    autocomplete_fields = ('company',)

    fieldsets = UserAdmin.fieldsets + (
        ('Role & Entreprise', {
            'fields': (
                'role_legacy', 'role', 'company',
                'phone_number', 'address',
            )
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role & Entreprise', {
            'fields': ('role_legacy', 'role', 'company')
        }),
    )

    def role_display(self, obj):
        if obj.role:
            return obj.role.nom
        return obj.role_legacy
    role_display.short_description = 'Role'
