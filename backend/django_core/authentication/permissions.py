from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminRole(BasePermission):
    """Admin role or superuser only."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_admin_role
        )


def module_de_la_vue(view):
    """ASEC11 — module (clé de ``PERMISSION_MODULE``) dont relève ``view``.

    Attribut explicite ``permission_module`` d'abord, sinon l'app de la classe
    de vue (``apps.<app>.…`` → ``<app>``) si — et seulement si — le registre
    des droits porte des codes pour ce module. ``None`` = vue de fondation /
    satellite sans codes propres (règle historique, cf. ``IsResponsableOrAdmin``
    et la liste figée du test de matrice)."""
    if view is None:
        return None
    explicite = getattr(view, 'permission_module', None)
    if explicite:
        return explicite
    from apps.roles.permissions_registre import PERMISSION_MODULE
    parties = (type(view).__module__ or '').split('.')
    app = parties[1] if parties[0] == 'apps' and len(parties) > 1 \
        else parties[0]
    return app if app in set(PERMISSION_MODULE.values()) else None


def codes_du_module(module):
    """ASEC11 — codes du registre rattachés au module ``module``."""
    from apps.roles.permissions_registre import PERMISSION_MODULE
    return frozenset(c for c, m in PERMISSION_MODULE.items() if m == module)


class IsResponsableOrAdmin(BasePermission):
    """Responsable or admin role — ET, pour un rôle fin, droit sur le MODULE.

    ASEC11 (C-ASEC-004) : ``is_responsable`` est vrai dès qu'un rôle porte UN
    code d'écriture, quel que soit son module — Commercial terrain (visites) et
    Admin RH (paie) passaient donc les écritures CRM/Ventes/Facturation/Stock.
    Désormais, pour un compte à rôle fin non administrateur, la vue doit
    relever d'un module où le rôle porte :
      * un code d'ÉCRITURE de ce module pour une méthode d'écriture ;
      * au moins un code de ce module (lecture comprise) pour une lecture.
    Toujours AU-DESSUS de ``is_responsable`` (jamais plus large qu'avant).
    Inchangés : superuser, palier administrateur, comptes hérités sans rôle
    fin, vues sans module résolu (``module_de_la_vue`` → None)."""
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_responsable):
            return False
        if getattr(user, 'is_superuser', False) \
                or getattr(user, 'is_admin_role', False):
            return True
        if not getattr(user, 'role_id', None):
            return True
        module = module_de_la_vue(view)
        if module is None:
            return True
        codes = codes_du_module(module) & set(user.role.permissions or [])
        if request.method in SAFE_METHODS:
            return bool(codes)
        return user._role_grants_write(codes)


class IsAdminOrResponsableTier(BasePermission):
    """Palier Administrateur OU Responsable (dérivé du nouveau rôle).

    Ouvre les écrans d'administration (Paramètres, Utilisateurs, Rôles) à
    l'Administrateur ET au Responsable — promu — mais JAMAIS au palier limité
    (Utilisateur ou rôle personnalisé type « Commercial »).

    À NE PAS confondre avec ``IsResponsableOrAdmin`` : celui-ci passe pour tout
    porteur de rôle (``is_responsable`` renvoie True dès qu'un rôle est posé),
    ce qui laisserait entrer le palier limité. Ici on s'appuie sur le palier de
    menu canonique pour bloquer précisément ce palier.
    """
    def has_permission(self, request, view):
        from .models import CustomUser
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, 'menu_tier', None) in (
                CustomUser.ROLE_ADMIN, CustomUser.ROLE_RESPONSABLE
            )
        )


class IsAnyRole(BasePermission):
    """Any authenticated INTERNAL user.

    NTPRT5 — exclut explicitement les comptes PORTAIL externes
    (``portee != interne``) : ``IsAnyRole`` garde des routes INTERNES (p. ex.
    les lectures CRM), qu'un compte portail ne doit jamais atteindre (il reçoit
    403). Un collaborateur interne (``portee == interne``, le défaut) est
    inchangé — aucune régression.
    """
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, 'portee', 'interne') == 'interne'
        )


def HasPermissionOrLegacy(code):
    """Permission ERP granulaire quand l'utilisateur porte un rôle fin ;
    comportement historique (responsable/admin) pour les comptes hérités
    sans rôle. C'est ce qui rend possible un rôle « lecture seule Stock »
    sans rien changer pour demo_admin / demo_resp.
    """
    class _HasPermissionOrLegacy(BasePermission):
        def has_permission(self, request, view):
            user = request.user
            if not (user and user.is_authenticated):
                return False
            if user.is_superuser:
                return True
            if getattr(user, 'role', None):
                return user.has_erp_permission(code)
            return user.is_responsable
    _HasPermissionOrLegacy.__name__ = f'HasPermissionOrLegacy_{code}'
    return _HasPermissionOrLegacy


def HasPermissionAndRole(code, *roles_autorises):
    """QG4 — permission ERP granulaire ET rôle nommé (liste blanche).

    Ne passe que si l'utilisateur porte la permission ERP ``code`` ET un rôle
    dont le nom figure dans ``roles_autorises``. Le superuser passe toujours.
    Contrairement à ``HasPermissionOrLegacy``, les comptes hérités SANS rôle
    fin sont REFUSÉS : c'est une garde de restriction (qui a le droit), pas
    une garde de compatibilité.

    Usage:
        permission_classes = [HasPermissionAndRole(
            'stock_creer', 'Directeur', 'Commercial responsable')]
    """
    class _HasPermissionAndRole(BasePermission):
        message = ('Action réservée aux rôles : '
                   + ', '.join(roles_autorises) + '.')

        def has_permission(self, request, view):
            user = request.user
            if not (user and user.is_authenticated):
                return False
            if user.is_superuser:
                return True
            role = getattr(user, 'role', None)
            if role is None or role.nom not in roles_autorises:
                return False
            return user.has_erp_permission(code)
    _HasPermissionAndRole.__name__ = f'HasPermissionAndRole_{code}'
    return _HasPermissionAndRole


def HasPermission(code):
    """
    Permission factory. Returns a DRF permission class that checks
    whether the user has a specific ERP permission code.

    Usage:
        permission_classes = [HasPermission('stock_voir')]
    """
    class _HasPermission(BasePermission):
        def has_permission(self, request, view):
            return bool(
                request.user
                and request.user.is_authenticated
                and request.user.has_erp_permission(code)
            )
    _HasPermission.__name__ = f'HasPermission_{code}'
    return _HasPermission
