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
