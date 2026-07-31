"""NTPRT5 — Enforcement du Portail EXTERNE self-service (client/fournisseur/
partenaire).

Ce module pose la garde RÉUTILISABLE ``IsPortalScopedUser`` que TOUT viewset
``/api/django/portail/*`` (client, fournisseur, partenaire) doit porter, ainsi
que les helpers de scoping. Il complète la FONDATION posée par NTPRT1
(``CustomUser.portee`` + ``portail_{client,fournisseur,partenaire}_id`` +
les 3 rôles système portail) sans jamais introduire un second système d'auth :
le login JWT standard est réutilisé tel quel.

La garde fait deux choses, en miroir l'une de l'autre :

(a) **Autorisation des routes portail** — ``IsPortalScopedUser`` n'accorde
    l'accès qu'à un utilisateur authentifié dont ``portee`` n'est PAS
    ``interne`` (un collaborateur interne n'entre jamais par un endpoint
    portail).
(b) **Scoping obligatoire** — ``portal_scope_id`` / ``scope_filter_kwargs``
    donnent l'id de rattachement (client/fournisseur/partenaire) à appliquer
    SYSTÉMATIQUEMENT à chaque queryset portail, afin qu'un compte ne voie
    JAMAIS que ses propres données.

Le refus SYMÉTRIQUE — un compte portail qui vise une route INTERNE
(``/api/django/crm/*``, ``/api/django/ventes/*``, …) reçoit 403 — n'est PAS
posé ici (une permission DRF ne garde que le endpoint qui la porte) mais au
niveau des DEUX gardes internes transverses qui laissaient auparavant passer
« tout utilisateur authentifié » : ``core.ScopedPermission`` (côté lecture sans
``read_permission``) et ``authentication.IsAnyRole``. Toutes deux excluent
désormais explicitement ``portee != interne``. Les endpoints COMMUNS essentiels
au portail (``auth/me``, ``auth/logout``, ``token``/``token/refresh``) restent
sur ``IsAuthenticated``/``AllowAny`` et demeurent donc joignables par un compte
portail — la frontière est nette.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

# Valeur canonique de ``CustomUser.portee`` pour un compte interne (défaut).
# Répliquée en littéral (jamais un import de ``authentication.models`` ici) pour
# garder ``apps.roles`` sans dépendance de démarrage — la valeur est figée par
# NTPRT1 (``CustomUser.PORTEE_INTERNE``).
PORTEE_INTERNE = 'interne'

# Portée du compte portail → champ de rattachement (string-ref) sur
# ``CustomUser``. JAMAIS un ForeignKey cross-app : seul l'entier de l'id cible.
PORTAL_SCOPE_FIELDS = {
    'portail_client': 'portail_client_id',
    'portail_fournisseur': 'portail_fournisseur_id',
    'portail_partenaire': 'portail_partenaire_id',
}


def is_portal_user(user):
    """True si ``user`` est un compte PORTAIL externe authentifié."""
    return bool(
        user
        and getattr(user, 'is_authenticated', False)
        and getattr(user, 'portee', PORTEE_INTERNE) != PORTEE_INTERNE
    )


def portal_scope_id(user):
    """Id de l'entité (client/fournisseur/partenaire) rattachée au compte, ou
    ``None`` si ``user`` n'est pas un compte portail ou n'a pas d'id lié."""
    if not is_portal_user(user):
        return None
    field = PORTAL_SCOPE_FIELDS.get(getattr(user, 'portee', PORTEE_INTERNE))
    if field is None:
        return None
    return getattr(user, field, None)


def scope_filter_kwargs(user):
    """Dict de filtrage bornant un queryset de ``CustomUser`` portail à SON
    entité, p. ex. ``{'portail_client_id': 42}``.

    Utile pour lister les comptes d'une même organisation portail (équipe —
    NTPRT17). Renvoie ``None`` si ``user`` n'est pas un compte portail lié : le
    caller DOIT alors renvoyer un queryset vide (``.none()``), jamais tout.
    """
    if not is_portal_user(user):
        return None
    portee = getattr(user, 'portee', PORTEE_INTERNE)
    field = PORTAL_SCOPE_FIELDS.get(portee)
    if field is None:
        return None
    value = getattr(user, field, None)
    if value is None:
        return None
    return {field: value}


class IsPortalScopedUser(BasePermission):
    """Garde RÉUTILISABLE des endpoints ``/api/django/portail/*``.

    N'accorde l'accès qu'à un compte PORTAIL externe authentifié
    (``portee != interne``) ; un collaborateur interne — ou un anonyme — est
    refusé (403/401). Le scoping par id lié est fourni par ``portal_scope_id`` /
    ``scope_filter_kwargs`` que le viewset applique à son queryset.
    """

    message = 'Accès réservé aux comptes du portail externe.'

    def has_permission(self, request, view):
        return is_portal_user(getattr(request, 'user', None))


# ─────────────────────────────────────────────────────────────────────────────
# NTPRT10/11/20/21/27 — Gardes par PORTÉE EXACTE (jamais « portail quelconque »)
# ─────────────────────────────────────────────────────────────────────────────
#
# ``IsPortalScopedUser`` ci-dessus accorde l'accès à N'IMPORTE QUEL compte
# portail. C'est le bon contrat pour une surface commune, mais PAS pour un
# endpoint métier : les devis d'un client ne doivent jamais être lisibles par un
# compte FOURNISSEUR ou PARTENAIRE, même authentifié « portail ». Les classes
# ci-dessous exigent donc :
#
#   (a) la portée EXACTE attendue par l'endpoint, ET
#   (b) un id de rattachement NON NUL — un compte portail orphelin (aucune
#       entité liée) doit voir RIEN, jamais tout : sans cette condition, un
#       filtre ``.filter(client_id=None)`` — ou pire, un filtre oublié — devient
#       une fuite silencieuse.

class _IsPortalUserOfScope(BasePermission):
    """Base : compte portail de la portée EXACTE ``portee_requise``, rattaché."""

    portee_requise = None
    message = 'Accès réservé aux comptes du portail concerné.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not is_portal_user(user):
            return False
        if getattr(user, 'portee', PORTEE_INTERNE) != self.portee_requise:
            return False
        return portal_scope_id(user) is not None


class IsPortalClientUser(_IsPortalUserOfScope):
    """Compte PORTAIL CLIENT rattaché à un client (NTPRT10/11)."""
    portee_requise = 'portail_client'


class IsPortalFournisseurUser(_IsPortalUserOfScope):
    """Compte PORTAIL FOURNISSEUR rattaché à un fournisseur (NTPRT20/21)."""
    portee_requise = 'portail_fournisseur'


class IsPortalPartenaireUser(_IsPortalUserOfScope):
    """Compte PORTAIL PARTENAIRE rattaché à un partenaire (NTPRT27)."""
    portee_requise = 'portail_partenaire'


class IsInternalWriterOrPortalClientOwner(BasePermission):
    """NTPRT10 — LECTURE d'un document par son propriétaire côté portail.

    Sert le cas « le client relit SON propre document sur le chemin canonique »
    (règle #4 : ``/proposal`` reste l'UNIQUE rendu PDF devis client — on ouvre
    ce chemin au client plutôt que d'en créer un second).

    Contrat, volontairement le plus restrictif qui satisfasse le besoin :

    * INTERNE — comportement d'``IsResponsableOrAdmin`` reproduit À
      L'IDENTIQUE (``user.is_responsable``) : aucun accès interne n'est élargi
      ni retiré ;
    * PORTAIL — uniquement la portée ``portail_client``, uniquement en méthode
      SÛRE (jamais une écriture par ce chemin), uniquement s'il est rattaché à
      un client, et — au niveau OBJET — uniquement si l'objet appartient
      EXACTEMENT à ce client (``obj.<owner_field> == portail_client_id``).

    ``has_object_permission`` n'est consultée par DRF que lorsque la vue appelle
    ``get_object()`` : tout endpoint portant cette garde DOIT le faire (c'est le
    cas de ``/proposal``). Le viewset borne en plus son queryset, de sorte qu'un
    document d'autrui répond 404 (aucun oracle d'existence) plutôt que 403.
    """

    owner_field = 'client_id'
    message = "Ce document n'est pas accessible depuis votre espace."

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and getattr(user, 'is_authenticated', False)):
            return False
        if is_portal_user(user):
            return (
                getattr(user, 'portee', PORTEE_INTERNE) == 'portail_client'
                and portal_scope_id(user) is not None
                and request.method in SAFE_METHODS
            )
        # Interne : strictement la garde historique de l'endpoint.
        return bool(getattr(user, 'is_responsable', False))

    def has_object_permission(self, request, view, obj):
        user = getattr(request, 'user', None)
        if not is_portal_user(user):
            # Interne : déjà tranché par has_permission (garde inchangée).
            return True
        scope = portal_scope_id(user)
        if scope is None:
            return False
        return getattr(obj, self.owner_field, None) == scope
