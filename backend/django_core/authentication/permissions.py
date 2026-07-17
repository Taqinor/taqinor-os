from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Admin role or superuser only."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_admin_role
        )


class IsResponsableOrAdmin(BasePermission):
    """Responsable or admin role."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_responsable
        )


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
