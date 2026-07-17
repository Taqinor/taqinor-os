"""Permissions & enforcement transverses de la couche fondation ``core``.

ODX4 — Enforcement API des modules désactivés
----------------------------------------------

``DisabledModuleMiddleware`` renvoie **404** sur les endpoints d'un module
EXPLICITEMENT désactivé pour la société de l'appelant. Le mapping préfixe
d'URL → clé de module est dérivé des manifests ODX2 (``core.modules``) : le
2ᵉ segment de ``/api/django/<segment>/…`` désigne le module.

Invariants (règle #4 et frontières intactes) :

* **Défaut = actif** : sans ligne ``ModuleToggle`` désactivée, le comportement
  est BYTE-IDENTIQUE à aujourd'hui (aucun 404 nouveau).
* **Exemptions** : les couches fondation (``authentication``, ``roles``,
  ``parametres``, ``core``, ``records``, ``customfields``, ``audit``,
  ``reporting`` global, ``imports``) ne se coupent jamais ; ``publicapi`` est
  géré par ses propres clés API ; les endpoints PUBLICS tokenisés
  (``/api/django/public/…``, ``/proposal``, webhooks) ne sont JAMAIS bloqués.
* **Multi-tenant** : seule la société qui a désactivé le module voit le 404 ;
  les autres sociétés ne sont pas affectées.

``core`` reste une couche de base : le middleware lit la clé de module par
attribut sur les ``AppConfig`` (via ``core.modules``) — aucune importation d'app
domaine.
"""
from __future__ import annotations

from django.http import JsonResponse
from rest_framework.permissions import SAFE_METHODS, BasePermission

# ─────────────────────────────────────────────────────────────────────────────
# YRBAC6/YRBAC7 — Registre central des champs sensibles
# ─────────────────────────────────────────────────────────────────────────────
# Noms de champs qui ne doivent JAMAIS apparaître dans un payload sérialisé /
# export / PDF rendu pour un rôle non autorisé. Chaque champ est associé au
# codename de permission qui SEUL autorise à le voir. Source unique de vérité
# réutilisée par le sweep anti-fuite (YRBAC6) et le mixin de masquage (YRBAC7).
SENSITIVE_FIELDS = {
    # Prix d'achat / coût fournisseur — jamais client-facing (règle produit).
    'prix_achat': 'prix_achat_voir',
    'prix_achat_unitaire': 'prix_achat_voir',
    'date_dernier_achat': 'prix_achat_voir',
    # Indicateurs de marge dérivés du coût d'achat.
    'marge': 'marge_voir',
    'marge_pct': 'marge_voir',
    'marge_brute': 'marge_voir',
    # Conditions revendeur / achat.
    'prix_revendeur': 'prix_achat_voir',
    # Rémunérations / données RH sensibles.
    'salaire': 'salaires_voir',
    'salaire_base': 'salaires_voir',
    'remuneration': 'salaires_voir',
    'salaire_net': 'salaires_voir',
    'salaire_brut': 'salaires_voir',
}


# Préfixes d'URL (2ᵉ segment de /api/django/<seg>/) TOUJOURS exemptés :
# couches fondation/techniques + surfaces publiques tokenisées. Un module
# absent de ce set ET absent des manifests installables reste, par prudence,
# non bloqué (défaut = actif).
EXEMPT_PREFIXES = frozenset({
    '',            # /api/django/token…, /auth… (authentication)
    'token',
    'admin',
    'auth',
    'roles',
    'parametres',
    'core',
    'records',
    'imports',       # dataimport
    'custom-fields',  # customfields
    'audit',
    'reporting',     # agrégat transverse — jamais coupé
    'contact',
    'publicapi',     # géré par ses propres clés API
    'public',        # endpoints publics tokenisés (jamais bloqués)
    'static',
})

# Préfixe d'URL → clé de module quand ils DIFFÈRENT du 2ᵉ segment brut.
# (Ex. l'URL est « gestion-projet » mais la clé de manifest est
# « gestion_projet ».) Les préfixes identiques à leur clé n'ont pas besoin
# d'entrée ici.
PREFIX_TO_MODULE = {
    'gestion-projet': 'gestion_projet',
}

# Racine commune de toutes les routes de l'API Django.
_API_ROOT = 'api/django/'


def _module_key_for_path(path):
    """Renvoie la clé de module gérant ``path``, ou ``None`` si exempté.

    ``path`` est le chemin de la requête (``request.path``). On extrait le 2ᵉ
    segment après ``api/django/``. Toute route hors ``api/django/`` ou dans les
    préfixes exemptés renvoie ``None`` (jamais bloquée).
    """
    p = path.lstrip('/')
    if not p.startswith(_API_ROOT):
        return None
    reste = p[len(_API_ROOT):]
    segment = reste.split('/', 1)[0]
    if segment in EXEMPT_PREFIXES:
        return None
    return PREFIX_TO_MODULE.get(segment, segment)


class DisabledModuleMiddleware:
    """Renvoie 404 sur les endpoints d'un module désactivé pour la société.

    Se place APRÈS l'authentification (pour lire ``request.user.company``).
    Sans utilisateur authentifié ou sans société, aucune action (défaut actif).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Ensemble des clés de modules réellement installables (issu des
        # manifests). Une clé absente de cet ensemble n'est jamais bloquée.
        self._installable_keys = None

    def _installable(self):
        if self._installable_keys is None:
            from . import modules as modules_infra
            try:
                manifests = modules_infra.collect_manifests()
            except Exception:  # noqa: BLE001 - jamais casser le pipeline HTTP
                manifests = {}
            self._installable_keys = {
                k for k, m in manifests.items() if m.get('installable')
            }
        return self._installable_keys

    def _company(self, request):
        """Résout la société de l'appelant, best-effort (jamais d'exception).

        L'authentification de l'API est portée par DRF (JWT via cookie/Bearer)
        et n'est PAS encore résolue au niveau middleware pour les requêtes API.
        On réutilise donc ``CookieJWTAuthentication`` ici — silencieusement : un
        jeton absent/invalide ⇒ pas de société ⇒ aucun blocage (défaut actif).
        """
        # Session Django déjà résolue (admin, tests) ?
        user = getattr(request, 'user', None)
        company = getattr(user, 'company', None)
        if company is not None:
            return company
        try:
            from authentication.cookie_auth import CookieJWTAuthentication
            result = CookieJWTAuthentication().authenticate(request)
        except Exception:  # noqa: BLE001 - jeton invalide ⇒ pas de blocage
            return None
        if result is None:
            return None
        return getattr(result[0], 'company', None)

    def __call__(self, request):
        key = _module_key_for_path(request.path)
        if key is not None and key in self._installable():
            company = self._company(request)
            if company is not None:
                from . import feature_flags
                if not feature_flags.module_actif(company, key):
                    return JsonResponse(
                        {'detail': 'Introuvable.'}, status=404)
        return self.get_response(request)


# ─────────────────────────────────────────────────────────────────────────────
# YRBAC5 — Permission scindée lecture/écriture par méthode HTTP
# ─────────────────────────────────────────────────────────────────────────────


def _user_has_or_legacy(user, code) -> bool:
    """Vrai si l'utilisateur porte la permission ERP ``code``.

    Repli HISTORIQUE (comme ``authentication.permissions.HasPermissionOrLegacy``)
    pour les comptes SANS rôle fin : un compte hérité (aucun ``role`` fin, ou
    palier Responsable/Admin) conserve l'accès qu'il avait avant l'introduction
    des permissions granulaires — on ne retire jamais un accès existant.
    """
    if not (user and user.is_authenticated):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    role = getattr(user, 'role', None)
    if role is None:
        # Compte légacy sans rôle fin : repli sur le comportement historique
        # (le palier Responsable/Admin conserve l'écriture ; les autres restent
        # gardés par le code appelant côté lecture).
        return bool(getattr(user, 'is_responsable', False))
    return user.has_erp_permission(code)


class ScopedPermission(BasePermission):
    """Permission « lecture ≠ écriture » pilotée par un mixin de viewset.

    Le viewset (via ``WriteScopedPermissionMixin``) expose ``read_permission``
    et ``write_permission`` ; cette classe route la vérification selon la
    méthode HTTP (méthode sûre → lecture, sinon → écriture). Un code de
    permission ``None`` signifie « aucune permission spécifique requise » pour
    ce côté (tout utilisateur authentifié passe), ce qui préserve le
    comportement historique quand seul le côté écriture est gardé.
    """

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        # NTPRT5 — un compte PORTAIL externe (``portee != interne``) n'accède
        # JAMAIS à une route INTERNE gardée par ScopedPermission, même côté
        # lecture sans ``read_permission`` (où « authentifié suffisait »).
        # Les endpoints portail portent leur propre garde
        # (``roles.IsPortalScopedUser``) ; les endpoints communs essentiels
        # (auth/me, logout, token) restent sur IsAuthenticated/AllowAny, non
        # affectés. Littéral ``interne`` — pas d'import cross-app depuis core.
        if getattr(user, 'portee', 'interne') != 'interne':
            return False
        if request.method in SAFE_METHODS:
            code = getattr(view, 'read_permission', None)
        else:
            code = getattr(view, 'write_permission', None)
        if code is None:
            # Aucun code requis de ce côté → authentifié suffit.
            return True
        return _user_has_or_legacy(user, code)


class WriteScopedPermissionMixin:
    """Mixin de viewset : gate lecture/écriture par méthode HTTP (YRBAC5).

    Usage::

        class ProduitViewSet(WriteScopedPermissionMixin, TenantMixin,
                             viewsets.ModelViewSet):
            read_permission = 'stock_voir'
            write_permission = 'stock_gerer'

    Les méthodes sûres (GET/HEAD/OPTIONS) exigent ``read_permission`` ; les
    méthodes non-sûres (POST/PUT/PATCH/DELETE) exigent ``write_permission``.
    Un côté à ``None`` = « authentifié suffit » (préserve l'historique). Le
    repli légacy des comptes sans rôle fin est conservé (cf.
    ``_user_has_or_legacy``).

    NB : ce mixin pose ``ScopedPermission`` comme unique ``permission_classes``
    par défaut ; un viewset qui a besoin d'un ``get_permissions`` par action
    (ex. destroy admin-only) peut surcharger ``get_permissions`` en appelant
    ``super().get_permissions()`` puis en ajustant l'action ciblée.

    BUG réel corrigé : ``get_permissions()`` renvoyait INCONDITIONNELLEMENT
    ``[ScopedPermission()]``, ignorant tout ``permission_classes=`` déclaré
    directement sur une ``@action`` (ex. ``campagne-revision`` réservée
    ``IsAdminRole`` dans ``contrats.views.ContratViewSet``) — DRF applique un
    tel override en posant ``self.permission_classes`` sur l'instance de vue
    AVANT l'appel à ``get_permissions()`` (voir ``ViewSetMixin.as_view()`` /
    ``action.kwargs``), mais l'ancienne implémentation ne le lisait jamais.
    Conséquence concrète : un Responsable (repli légacy ``is_responsable`` via
    ``contrat_gerer``) passait la garde ``ScopedPermission`` en écriture sur
    ``campagne-revision``, alors que l'action est censée être STRICTEMENT
    réservée aux Administrateurs — un contournement RBAC réel, pas juste un
    test caduc. On respecte maintenant un override d'instance (différent du
    défaut de la classe) en retombant sur le comportement standard DRF.
    """

    read_permission = None
    write_permission = None
    permission_classes = [ScopedPermission]

    def get_permissions(self):
        # Un override d'instance posé par DRF pour CETTE action (ex.
        # `@action(permission_classes=[IsAdminRole])`) diffère du défaut de
        # classe : on le respecte au lieu de l'écraser par ScopedPermission.
        if self.permission_classes != type(self).permission_classes:
            return [permission() for permission in self.permission_classes]
        return [ScopedPermission()]
