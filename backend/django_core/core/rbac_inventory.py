"""Inventaire des permissions d'endpoint (YRBAC1).

Parcourt l'URLconf racine et, pour chaque vue/action DRF résolue, expose la
liste des ``permission_classes`` effectivement déclarées. Sert de source de
complétude :

* au test-inventaire YRBAC1 (``core/tests/test_endpoint_permission_inventory.py``),
  qui échoue si un endpoint résout à ``AllowAny`` seul hors allowlist ;
* à la matrice endpoint×rôle YRBAC2 (complétude des lignes) ;
* au durcissement des endpoints publics YRBAC9 (throttle/expiry).

``core`` reste FONDATION : ce module n'importe aucune app métier — il lit le
graphe d'URL déjà monté par Django et introspecte les attributs de classe.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.permissions import AllowAny, IsAuthenticated


@dataclass(frozen=True)
class EndpointPermissions:
    """Permissions déclarées pour un endpoint (préfixe URL + vue)."""
    pattern: str
    view_name: str
    permission_classes: tuple[str, ...]
    http_methods: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_allow_any(self) -> bool:
        return self.permission_classes == ("AllowAny",)

    @property
    def is_default_only(self) -> bool:
        """True si la seule permission est le défaut fourre-tout IsAuthenticated."""
        return self.permission_classes == ("IsAuthenticated",)


# Marqueur de segment : tout endpoint dont le chemin porte un segment
# ``public`` (…/public/…, …/public) est un lien tokenisé légitime — c'est la
# convention du repo (les blueprints publics vivent tous sous un segment
# ``public`` distinct des routeurs authentifiés).
_PUBLIC_SEGMENT = "public"

# Endpoints AllowAny légitimes qui n'ont PAS de segment ``public`` dans leur
# chemin (par nature publics/tokenisés). Toute NOUVELLE vue AllowAny hors de
# cette liste ET sans segment ``public`` fait échouer le test YRBAC1.
PUBLIC_ALLOWLIST_PREFIXES = (
    "api/django/token",                       # obtention/refresh/verify JWT
    "api/django/contact",                     # formulaire de contact (park-able)
    "api/django/reporting/calendar",          # flux ICS calendrier tokenisé
    "api/django/rh/pointages/kiosque",        # guichet kiosque device-PIN throttlé
    "api/django/rh/promesses-embauche",       # promesse d'embauche tokenisée
    "api/django/gestion-projet/portail",      # portail avancement/CSAT tokenisé
    "api/django/notifications/push/vapid-public-key",  # clé VAPID (publique par nature)
    "api/django/identity/login-banner",       # NTSEC28 — bannière/mention légale pré-auth (AllowAny)
    # NTSEC5/6 — provisioning SCIM 2.0 (Users/Groups) : endpoints machine-à-
    # machine authentifiés par un jeton porteur ScimToken dédié (jamais le JWT
    # humain), scopés société via le company_slug de l'URL. AllowAny au niveau
    # DRF car l'auth Bearer SCIM + le scope tenant sont gérés dans la vue.
    "api/django/identity/scim",
    "api/django/health",                      # sondes liveness/readiness
    # Marketing PUBLIC (compta.urls) — tokenisés/webhooks, sans login, throttlés :
    "api/django/compta/webhooks/",            # webhooks entrants Brevo/SMS-STOP
    "api/django/compta/desinscription/",      # désinscription tokenisée (opt-out)
    "api/django/compta/double-optin/",        # confirmation double opt-in tokenisée
    "api/django/compta/r/",                   # redirection de lien tracké tokenisée
    "api/django/compta/enquetes-publiques/",  # enquête/NPS publique tokenisée
    "api/django/compta/reponses-enquete/",    # certificat PDF d'une réponse d'enquête
    "api/django/compta/evenements-marketing/",  # inscription publique à un événement
    "api/django/rh/carrieres",                # page carrières publique (flag-gated)
    # Auth publiques (JWT obtention/refresh, inscription société onboarding) :
    "api/django/auth/token",                  # obtention/refresh/verify JWT (auth.urls)
    "api/django/auth/register-company",       # inscription société (onboarding)
    # Sondes/metrics montées sous core/ (déplacées depuis /health) :
    "api/django/core/health",                 # sondes liveness/readiness
    "api/django/core/metrics",                # métriques (probe monitoring)
    # Portail client compta tokenisé (relevé/factures via jeton, sans login) :
    "api/django/compta/portail",
    # Liens GED tokenisés (dépôt/signature électronique, sans login) :
    "api/django/ged/depot",
    "api/django/ged/signataire",
    "api/django/ged/signature",
    # Proposition de devis tokenisée (client, sans login — cf. RÈGLE #4 /proposal) :
    "api/django/ventes/proposal",
    # QX34 — suivi post-signature public en lecture seule, tokenisé (ShareLink),
    # alias sous le mount ventes/ (la même vue vit aussi sous public/). Sans login.
    "api/django/ventes/suivi",
    # Marketing PUBLIC (ODX10 — nouveau préfixe /marketing/, miroir de /compta/) :
    "api/django/marketing/webhooks/",         # webhooks entrants Brevo/SMS-STOP
    "api/django/marketing/desinscription/",   # désinscription tokenisée (opt-out)
    "api/django/marketing/double-optin/",     # confirmation double opt-in tokenisée
    "api/django/marketing/r/",                # redirection de lien tracké tokenisée
    "api/django/marketing/enquetes-publiques/",  # enquête/NPS publique tokenisée
    "api/django/marketing/reponses-enquete/",  # certificat PDF d'une réponse d'enquête
    "api/django/marketing/evenements-marketing/",  # inscription publique à un événement
    # Kiosque pointage : le motif routeur capture une ancre ^ dans le chemin :
    "api/django/rh/^pointages/kiosque",
    "api/schema",                             # OpenAPI (si activé plus tard)
    "api/docs",
    "api/redoc",
)


def _permission_class_names(view_class) -> tuple[str, ...]:
    """Noms des ``permission_classes`` déclarées sur une classe de vue.

    Lit l'attribut de classe (statique) — le plus fiable sans requête réelle.
    Un ``get_permissions`` par action reste résolu à l'exécution ; ce parcours
    statique remonte la garde DÉCLARÉE au niveau vue, ce qui suffit à détecter
    un ``AllowAny`` seul ou l'absence de garde métier.
    """
    perms = getattr(view_class, "permission_classes", None)
    if not perms:
        return tuple()
    return tuple(sorted(p.__name__ for p in perms))


def _iter_patterns(patterns, prefix=""):
    for entry in patterns:
        if isinstance(entry, URLResolver):
            new_prefix = prefix + str(entry.pattern)
            yield from _iter_patterns(entry.url_patterns, new_prefix)
        elif isinstance(entry, URLPattern):
            yield prefix + str(entry.pattern), entry


def build_inventory() -> list[EndpointPermissions]:
    """Recense chaque endpoint DRF résoluble et ses permissions déclarées."""
    inventory: list[EndpointPermissions] = []
    seen: set[tuple[str, str]] = set()
    resolver = get_resolver()
    for full_pattern, url_pattern in _iter_patterns(resolver.url_patterns):
        callback = url_pattern.callback
        view_class = getattr(callback, "cls", None) or getattr(
            callback, "view_class", None)
        if view_class is None:
            continue
        # Restreindre aux vues DRF (portent permission_classes / .as_view DRF).
        if not hasattr(view_class, "permission_classes"):
            continue
        perms = _permission_class_names(view_class)
        # Les vues sans permission_classes explicite héritent le défaut DRF
        # (IsAuthenticated) — on le matérialise pour la lisibilité.
        if not perms:
            perms = ("IsAuthenticated",)
        methods = tuple(sorted(getattr(callback, "actions", {}) or {}))
        key = (full_pattern, view_class.__name__)
        if key in seen:
            continue
        seen.add(key)
        inventory.append(EndpointPermissions(
            pattern=full_pattern,
            view_name=view_class.__name__,
            permission_classes=perms,
            http_methods=methods,
        ))
    inventory.sort(key=lambda e: (e.pattern, e.view_name))
    return inventory


def _is_allowlisted(pattern: str) -> bool:
    # Un segment ``public`` dans le chemin = lien tokenisé légitime (convention
    # du repo). Sinon, le préfixe doit figurer dans l'allowlist explicite.
    segments = pattern.strip("/").split("/")
    if _PUBLIC_SEGMENT in segments:
        return True
    return any(pattern.startswith(p) for p in PUBLIC_ALLOWLIST_PREFIXES)


def offending_allow_any(inventory=None) -> list[EndpointPermissions]:
    """Endpoints résolus à ``AllowAny`` seul HORS allowlist publique."""
    if inventory is None:
        inventory = build_inventory()
    return [
        e for e in inventory
        if e.is_allow_any and not _is_allowlisted(e.pattern)
    ]


def render_inventory_markdown(inventory=None) -> str:
    """Rend l'inventaire en Markdown (artefact ``docs/rbac-endpoint-inventory.md``)."""
    if inventory is None:
        inventory = build_inventory()
    lines = [
        "# Inventaire des permissions d'endpoint (YRBAC1)",
        "",
        "Régénéré par `core/tests/test_endpoint_permission_inventory.py`.",
        "Ne pas éditer à la main : lancer le test pour rafraîchir.",
        "",
        "| Endpoint | Vue | Permissions | Méthodes |",
        "| --- | --- | --- | --- |",
    ]
    for e in inventory:
        methods = ", ".join(e.http_methods) if e.http_methods else "—"
        perms = ", ".join(e.permission_classes)
        lines.append(f"| `{e.pattern}` | {e.view_name} | {perms} | {methods} |")
    lines.append("")
    return "\n".join(lines)


# Ré-exports pratiques.
__all__ = [
    "EndpointPermissions",
    "PUBLIC_ALLOWLIST_PREFIXES",
    "build_inventory",
    "offending_allow_any",
    "render_inventory_markdown",
    "AllowAny",
    "IsAuthenticated",
]
