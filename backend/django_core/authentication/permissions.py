from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAuthenticatedInterne(BasePermission):
    """ASEC51 (C-ASEC-017) — permission DRF PAR DÉFAUT (``REST_FRAMEWORK
    ['DEFAULT_PERMISSION_CLASSES']``) : compte authentifié ET INTERNE.

    Avant, le défaut était ``IsAuthenticated`` : toute vue sans
    ``permission_classes`` explicite s'ouvrait à un compte PORTAIL externe
    (client / fournisseur / partenaire) dès qu'il avait un JWT. Désormais une
    vue n'est joignable par un compte portail QUE si elle le déclare
    explicitement (gardes ``IsPortal*`` des endpoints ``/portail/*``, ou un
    ``IsAuthenticated`` explicite comme ``/auth/me/``, ``/auth/logout/``,
    ``/auth/change-password/``).

    Lit le marqueur portail EXISTANT de ``CustomUser`` (``portee``, défaut
    ``interne``) — aucune seconde notion de « compte interne », aucun import
    d'``apps.*`` (``authentication`` reste une app de fondation). Un anonyme
    reste refusé exactement comme par ``IsAuthenticated`` (401)."""

    message = 'Accès réservé aux comptes internes.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        interne = getattr(type(user), 'PORTEE_INTERNE', 'interne')
        return getattr(user, 'portee', interne) == interne


class EcritureRefuseeLectureSeule(BasePermission):
    """APUB13 — refuse les écritures CRUD à un rôle fin sans aucune écriture
    (Viewer, Utilisateur) ; ``run``/``donnees`` restent des lectures."""

    ACTIONS = frozenset({'create', 'update', 'partial_update', 'destroy'})
    message = 'Votre rôle est en lecture seule.'

    def has_permission(self, request, view):
        user = request.user
        if getattr(view, 'action', None) not in self.ACTIONS or not getattr(user, 'role_id', None):
            return True
        return user.is_superuser or user._role_grants_write(user.role.permissions or [])


class IsAdminRole(BasePermission):
    """Admin role or superuser only."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_admin_role
        )


# ASEC11-lint — registre module→codes INJECTÉ par ``apps.roles`` depuis son
# ``AppConfig.ready()`` (``enregistrer_registre_modules``). ``authentication``
# est une app de fondation importée par ``core`` : elle ne doit avoir AUCUNE
# arête d'import vers ``apps.*`` (contrat « core imports downward only »). On
# garde une RÉFÉRENCE au dict (jamais une copie) : comportement identique à
# l'ancien import fonction-local de ``PERMISSION_MODULE``.
_REGISTRE_MODULES = None

#: APFS28 (D-APFS-4) — lectures CROISÉES admises : ``{(module, nom de la
#: classe de vue): frozenset(codes)}`` injecté par ``apps.roles`` (jamais
#: importé d'ici) ; lu par ``LectureDuModule``.
_OCTROIS_LECTURE = {}


def enregistrer_registre_modules(permission_module, *, octrois_lecture=None):
    """Branché par ``apps.roles.apps.RolesConfig.ready()`` avec
    ``apps.roles.permissions_registre.PERMISSION_MODULE`` (et, APFS28,
    ``OCTROIS_LECTURE``)."""
    global _REGISTRE_MODULES, _OCTROIS_LECTURE
    _REGISTRE_MODULES = permission_module
    if octrois_lecture is not None:
        _OCTROIS_LECTURE = octrois_lecture


def _registre_modules():
    if _REGISTRE_MODULES is None:
        from django.core.exceptions import ImproperlyConfigured
        # Jamais de repli silencieux : un registre absent dégraderait la garde
        # ASEC11 vers la règle historique (plus permissive).
        raise ImproperlyConfigured(
            'Registre des modules de permissions non enregistré : '
            "'apps.roles' doit figurer dans INSTALLED_APPS (son ready() "
            'appelle authentication.permissions.enregistrer_registre_modules).')
    return _REGISTRE_MODULES


#: AARG52 — apps de FONDATION sans codes au registre : seules à garder la règle
#: historique en ÉCRITURE (liste qui ne fait que décroître ; ``portail`` retiré ;
#: ``monitoring`` retiré par AMON92, ses vues relevant du module ``sav``, AMON45 ;
#: ``semantic`` retiré par APFS43 : ses métriques ne s'écrivent plus par un
#: rôle fin non administrateur).
APPS_SANS_MODULE = frozenset({
    'authentication', 'core', 'dataimport', 'documents',
    'offlinesync', 'outillage', 'records', 'roles', 'uxviews'})

#: ODX18 — apps dont les vues relèvent du module de droits d'une AUTRE app.
#: ``apps.facturation`` n'a pas de codes propres (ASEC9 : « module
#: facturation » = module ``ventes``, cf. ``'encaisser': 'ventes'`` du
#: registre) ; ses vues déménagées de ``apps.ventes`` gardent donc la garde
#: ``ventes`` à l'identique au lieu de retomber sur « module non résolu ».
MODULE_DES_APPS = {'facturation': 'ventes'}


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
    return module_du_chemin(type(view).__module__)


def module_du_chemin(chemin):
    """APFS4 — module de droits d'un chemin Python (``apps.<app>.…`` → ``<app>``,
    ``MODULE_DES_APPS`` appliqué) s'il porte des codes au registre ; sinon ``None``."""
    PERMISSION_MODULE = _registre_modules()
    parties = (chemin or '').split('.')
    app = parties[1] if parties[0] == 'apps' and len(parties) > 1 \
        else parties[0]
    app = MODULE_DES_APPS.get(app, app)
    return app if app in set(PERMISSION_MODULE.values()) else None


def peut_lire_module(user, module):
    """APFS4 — LA règle de lecture d'un module (branche lecture
    d'``IsResponsableOrAdmin``, reprise par le moteur de données)."""
    if getattr(user, 'is_superuser', False) or getattr(user, 'is_admin_role', False) \
            or not getattr(user, 'role_id', None) or module is None:
        return True
    return bool(codes_du_module(module) & set(user.role.permissions or []))


def codes_du_module(module):
    """ASEC11 — codes du registre rattachés au module ``module``."""
    PERMISSION_MODULE = _registre_modules()
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
    fin, lectures sans module résolu ; écriture sans module résolu :
    ``APPS_SANS_MODULE`` seulement (AARG52)."""
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
        if request.method in SAFE_METHODS:
            return peut_lire_module(user, module)
        if module is None:
            parties = (type(view).__module__ or '').split('.')
            app = parties[1] if parties[0] == 'apps' and len(parties) > 1 else parties[0]
            return app in APPS_SANS_MODULE
        return user._role_grants_write(codes_du_module(module) & set(user.role.permissions or []))


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


class LectureDuModule(IsAnyRole):
    """APFS28 (D-APFS-4, C-APFS-080) — LECTURE d'une vue de module.

    Compte interne (``IsAnyRole``) ET, pour un rôle fin non administrateur, au
    moins un code du module de la vue (``module_de_la_vue``) OU un code
    octroyé pour CETTE vue (``OCTROIS_LECTURE`` : le Commercial lit les
    chantiers de ses ventes, le Technicien les lignes / dossiers / recette du
    devis de son chantier). Inchangés : superuser, palier administrateur,
    compte hérité sans rôle fin, module non résolu (règle d'``IsAnyRole``) ;
    compte portail refusé."""

    message = 'Accès réservé aux rôles du module.'
    #: APFS108 — module FIGÉ (``LectureVentes``) au lieu du module de la vue.
    module_fige = None

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        if (getattr(user, 'is_superuser', False)
                or getattr(user, 'is_admin_role', False)
                or not getattr(user, 'role_id', None)):
            return True
        module = self.module_fige or module_de_la_vue(view)
        if module is None:
            return True
        perms = set(user.role.permissions or [])
        if codes_du_module(module) & perms:
            return True
        octroi = _OCTROIS_LECTURE.get((module, type(view).__name__), ())
        return bool(set(octroi) & perms)


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


# ── APFS3 / AUD139 — mot de passe à changer ─────────────────────────────────
# Déplacé depuis ``apps.roles.permissions`` (qui le ré-importe) : la garde est
# appliquée au point UNIQUE d'authentification JWT (``cookie_auth``), pour tout
# compte — interne comme portail —, hors les trois vues qui permettent de
# SORTIR de cet état (``VUES_ADMISES_MOT_DE_PASSE_A_CHANGER``).
#: Code machine renvoyé dans le corps du 403 (le frontend s'y branche).
CODE_MOT_DE_PASSE_A_CHANGER = 'mot_de_passe_a_changer'

MESSAGE_MOT_DE_PASSE_A_CHANGER = (
    'Vous devez définir un nouveau mot de passe avant d’accéder à votre '
    'espace.'
)


def exiger_mot_de_passe_change(user):
    """AUD139 — Lève 403 si ``user`` doit encore changer son mot de passe.

    Le corps porte un CODE exploitable (``code``) en plus du message : un
    écran ne doit pas avoir à reconnaître une phrase française pour router
    l'utilisateur vers le formulaire de changement.
    """
    if getattr(user, 'must_change_password', False):
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied({
            'detail': MESSAGE_MOT_DE_PASSE_A_CHANGER,
            'code': CODE_MOT_DE_PASSE_A_CHANGER,
        })


#: APFS3 — les vues joignables tant que le mot de passe n'est pas changé
#: (nom qualifié de la classe de vue).
VUES_ADMISES_MOT_DE_PASSE_A_CHANGER = frozenset({
    'authentication.views.MeView',
    'authentication.views.LogoutView',
    'authentication.views.ChangePasswordView',
})


def exiger_mot_de_passe_change_hors_sortie(request, user):
    """APFS3 — ``exiger_mot_de_passe_change`` sur une requête DRF dont la vue
    n'est pas une des trois portes de sortie ; une ``HttpRequest`` nue (les
    middlewares) n'est jamais refusée ici."""
    from rest_framework.request import Request

    if not isinstance(request, Request):
        return
    vue = (getattr(request, 'parser_context', None) or {}).get('view')
    if vue is None:
        return
    nom = f'{type(vue).__module__}.{type(vue).__qualname__}'
    if nom not in VUES_ADMISES_MOT_DE_PASSE_A_CHANGER:
        exiger_mot_de_passe_change(user)


def est_operateur_plateforme(user):
    """APFS61 (D-APFS-2) — LE prédicat « opérateur de la plateforme » :
    superutilisateur SANS société (celui de ``core.mixins.company_qs``). Un
    superutilisateur rattaché à une société est borné à elle."""
    attache = getattr(user, '_company_id_attache',
                      getattr(user, 'company_id', None))
    return bool(user is not None
                and getattr(user, 'is_authenticated', False)
                and getattr(user, 'is_superuser', False)
                and not attache)


class PeutReinitialiserDemo(BasePermission):
    """NTDMO32 — qui peut déclencher ``reset-demo/`` : un compte ``is_staff``
    (accès historique) ou un rôle portant ``peut_reinitialiser_demo``."""

    message = "Réservé aux comptes autorisés à réinitialiser la démo."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return bool(getattr(user, 'is_staff', False)
                    or user.has_erp_permission('peut_reinitialiser_demo'))
