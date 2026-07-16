"""NTSEC11 — Middleware d'allowlist IP / CIDR par société.

Fondation, NO-OP par défaut. Pour une requête authentifiée dont la société
porte une ``NetworkPolicy`` active :

* mode ``enforce`` — si l'IP appelante n'est dans AUCUNE plage autorisée,
  la requête est refusée (403) ;
* mode ``monitor`` — la requête passe mais une ``SECURITY_ALERT`` est
  journalisée (best-effort, via l'entonnoir d'audit) ;
* mode ``off`` (ou pas de politique) — comportement historique, inchangé.

Les endpoints PUBLICS (webhooks, estimateur public, ``/proposal`` tokenisé,
formulaires publics) ne sont JAMAIS soumis à l'allowlist : ils n'ont pas de
société authentifiée et doivent rester joignables depuis Internet.

L'authentification DRF (JWT cookie/Bearer) n'est pas résolue au niveau
middleware : on réutilise ``CookieJWTAuthentication`` en best-effort, comme
``core.permissions.DisabledModuleMiddleware``. Un jeton absent/invalide ⇒
aucune société ⇒ aucun blocage.
"""
import ipaddress
import logging

from django.http import JsonResponse

logger = logging.getLogger(__name__)

# Fragments de chemin JAMAIS soumis à l'allowlist (endpoints publics).
_PUBLIC_PATH_MARKERS = (
    '/api/public/',
    '/public/',
    '/proposal',
    '/webhook',
    '/estimateur',
)


def _is_public_path(path):
    return any(marker in path for marker in _PUBLIC_PATH_MARKERS)


def _client_ip(request):
    """IP de l'appelant. Derrière notre reverse-proxy (nginx/Caddy),
    ``REMOTE_ADDR`` est celle du proxy : on prend donc le premier saut de
    ``X-Forwarded-For`` quand il est présent, sinon ``REMOTE_ADDR``.
    """
    meta = getattr(request, 'META', {}) or {}
    forwarded = meta.get('HTTP_X_FORWARDED_FOR', '') or ''
    if forwarded:
        first = forwarded.split(',')[0].strip()
        if first:
            return first
    return meta.get('REMOTE_ADDR', '') or ''


def _ip_allowed(ip_str, policy):
    """Vrai si ``ip_str`` appartient à au moins une plage de la politique.

    Best-effort : une IP illisible ou une plage cassée ne fait jamais planter
    la requête. Une IP illisible est traitée comme NON autorisée (en enforce,
    on préfère refuser une IP qu'on ne sait pas situer).
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for rule in policy.rules.all():
        try:
            net = ipaddress.ip_network((rule.cidr or '').strip(),
                                       strict=False)
        except ValueError:
            continue
        if addr in net:
            return True
    return False


def _is_admin(user):
    return bool(
        getattr(user, 'is_superuser', False)
        or getattr(user, 'is_admin_role', False)
    )


class NetworkPolicyMiddleware:
    """Applique l'allowlist réseau par société (NTSEC11)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def _resolve(self, request):
        """(user, company) best-effort — jamais d'exception."""
        user = getattr(request, 'user', None)
        company = getattr(user, 'company', None)
        if company is not None:
            return user, company
        try:
            from authentication.cookie_auth import CookieJWTAuthentication
            result = CookieJWTAuthentication().authenticate(request)
        except Exception:  # noqa: BLE001 - jeton invalide ⇒ pas de blocage
            return None, None
        if result is None:
            return None, None
        resolved = result[0]
        return resolved, getattr(resolved, 'company', None)

    def _policy_for(self, company):
        try:
            from .models import NetworkPolicy
            return (
                NetworkPolicy.objects
                .filter(company=company)
                .prefetch_related('rules')
                .first()
            )
        except Exception:  # noqa: BLE001 - jamais casser le pipeline HTTP
            logger.debug('identity: lecture NetworkPolicy échouée',
                         exc_info=True)
            return None

    def _audit_blocked(self, user, company, ip, path, blocked):
        try:
            from apps.audit.models import AuditLog
            from apps.audit.recorder import record
            verbe = 'refusée' if blocked else 'signalée'
            record(
                AuditLog.Action.SECURITY_ALERT,
                user=user,
                company=company,
                detail=(f'Allowlist IP : requête {verbe} depuis {ip} '
                        f'(hors plage autorisée) sur {path}.'),
            )
        except Exception:  # noqa: BLE001 - journalisation best-effort
            logger.debug('identity: audit allowlist indisponible',
                         exc_info=True)

    def __call__(self, request):
        path = getattr(request, 'path', '') or ''
        if _is_public_path(path):
            return self.get_response(request)

        user, company = self._resolve(request)
        if company is None:
            # Pas de société authentifiée → jamais bloqué (défaut inerte).
            return self.get_response(request)

        policy = self._policy_for(company)
        from .models import NetworkPolicy
        if policy is None or policy.mode == NetworkPolicy.Mode.OFF:
            return self.get_response(request)

        # Un superuser SANS société (acteur plateforme) n'est jamais concerné.
        if policy.applies_to == NetworkPolicy.AppliesTo.ADMINS \
                and not _is_admin(user):
            return self.get_response(request)

        ip = _client_ip(request)
        if _ip_allowed(ip, policy):
            return self.get_response(request)

        if policy.mode == NetworkPolicy.Mode.ENFORCE:
            self._audit_blocked(user, company, ip, path, blocked=True)
            return JsonResponse(
                {'detail': 'Adresse IP non autorisée par la politique '
                           'réseau de votre société.'},
                status=403,
            )

        # mode == MONITOR : on journalise sans bloquer.
        self._audit_blocked(user, company, ip, path, blocked=False)
        return self.get_response(request)
