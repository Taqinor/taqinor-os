"""Authentification, permissions et throttling de l'API publique (N89).

L'API publique n'utilise PAS la session/JWT : elle s'authentifie par clé d'API
portée dans l'en-tête « Authorization: Api-Key <clé> ». La clé appartient à une
société ; toute requête authentifiée par clé est donc scopée à CETTE société,
côté serveur, jamais depuis le corps de la requête.
"""
from django.utils import timezone

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import authentication, exceptions, permissions
from rest_framework.throttling import SimpleRateThrottle

from .models import ApiKey, hash_key

AUTH_KEYWORD = 'Api-Key'


class ApiKeyUser:
    """Acteur léger anonyme représentant une clé d'API.

    DRF exige un objet `request.user` ; on n'a pas d'utilisateur connecté, donc
    on expose un porteur minimal non authentifié au sens session. La société et
    les scopes sont portés par `request.auth` (l'instance ApiKey).
    """
    is_authenticated = False  # pas un utilisateur de session
    is_anonymous = True

    def __init__(self, api_key):
        self.api_key = api_key
        self.company = api_key.company
        self.company_id = api_key.company_id

    def __str__(self):
        return f'ApiKey<{self.api_key.prefix}…>'


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Lit « Authorization: Api-Key <clé> », résout la société, pose le scope.

    Renvoie (ApiKeyUser, ApiKey) ; `request.auth` est l'instance ApiKey, qui
    porte company + scopes. Rejette une clé absente du système ou désactivée.
    """

    keyword = AUTH_KEYWORD

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode('latin-1')
        if not header:
            return None  # laisse les autres classes / l'anonyme jouer
        parts = header.split()
        if parts[0].lower() != self.keyword.lower():
            return None  # autre schéma (Bearer…) — pas pour nous
        if len(parts) == 1:
            raise exceptions.AuthenticationFailed('Clé API manquante.')
        if len(parts) > 2:
            raise exceptions.AuthenticationFailed('En-tête Api-Key invalide.')

        raw_key = parts[1]
        try:
            api_key = ApiKey.objects.select_related('company').get(
                key_hash=hash_key(raw_key))
        except ApiKey.DoesNotExist:
            raise exceptions.AuthenticationFailed('Clé API invalide.')
        if not api_key.enabled:
            raise exceptions.AuthenticationFailed('Clé API désactivée.')
        # NTAPI23 — la grace period de rotation est TERMINÉE : une clé
        # au-delà de `expire_le` est rejetée comme n'importe quelle clé
        # désactivée (la nouvelle clé émise par `rotate()` continue de
        # fonctionner sans interruption).
        if api_key.est_expiree:
            raise exceptions.AuthenticationFailed(
                'Clé API expirée (période de grâce de rotation terminée).')

        # Trace d'usage (best-effort, non bloquant).
        ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

        return (ApiKeyUser(api_key), api_key)

    def authenticate_header(self, request):
        return self.keyword


class QueryTokenAuthentication(authentication.BaseAuthentication):
    """NTAPI30 — lit ``?token=<clé>`` (paramètre de requête, PAS un en-tête).

    Réservée aux endpoints où le CLIENT ne peut poser aucun en-tête custom —
    typiquement ``=IMPORTDATA()`` de Google Sheets/Excel Web, qui ne fait
    qu'un GET brut sur une URL collée dans une cellule. Mêmes garde-fous que
    ``ApiKeyAuthentication`` (clé inconnue/désactivée/expirée → 401) ; la
    RESTRICTION lecture-seule (scope ``read:*`` uniquement) est imposée par
    la vue elle-même (vérification explicite du scope requis, jamais ici) —
    un token exposé dans une URL (log serveur, historique navigateur, cellule
    partagée) ne doit JAMAIS pouvoir déclencher une écriture."""

    def authenticate(self, request):
        raw_key = request.query_params.get('token')
        if not raw_key:
            return None  # laisse les autres classes / l'anonyme jouer
        try:
            api_key = ApiKey.objects.select_related('company').get(
                key_hash=hash_key(raw_key))
        except ApiKey.DoesNotExist:
            raise exceptions.AuthenticationFailed('Jeton invalide.')
        if not api_key.enabled:
            raise exceptions.AuthenticationFailed('Jeton désactivé.')
        if api_key.est_expiree:
            raise exceptions.AuthenticationFailed('Jeton expiré.')
        ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())
        return (ApiKeyUser(api_key), api_key)

    def authenticate_header(self, request):
        """Challenge `WWW-Authenticate` — SANS lui, « pas de jeton » devient 403.

        DRF ne rend un 401 (`NotAuthenticated`/`AuthenticationFailed`) que si le
        PREMIER authenticator de la vue expose un en-tête d'authentification
        (`APIView.handle_exception`) ; sinon il rétrograde en 403. Cette classe
        n'en déclarait aucun : jeton absent, invalide, désactivé ou expiré
        répondait 403 « droits insuffisants » au lieu de 401 « justificatif
        manquant/refusé » — le client (Google Sheets) ne pouvait plus distinguer
        « clé à renouveler » de « scope manquant », et l'API publique
        contredisait son propre contrat NTAPI30. Le paramètre attendu est
        annoncé pour que la réponse reste auto-descriptive.
        """
        return 'Query realm="api-public", param="token"'


class HasApiScope(permissions.BasePermission):
    """Exige que la clé porte le scope déclaré sur la vue (`required_scope`)."""

    message = 'Cette clé API n’a pas le droit nécessaire.'

    def has_permission(self, request, view):
        api_key = getattr(request, 'auth', None)
        if not isinstance(api_key, ApiKey):
            return False
        required = getattr(view, 'required_scope', None)
        if not required:
            return False
        return api_key.has_scope(required)


# NTAPI6 — attribut posé sur la requête par le throttle et lu par
# `public_response.PublicApiResponseMixin` pour écrire les en-têtes
# `X-RateLimit-*` (et `Retry-After` sur 429). Passer par la requête plutôt
# qu'un état d'instance : DRF instancie un throttle NEUF par requête, mais la
# vue qui finalise la réponse n'y a aucun accès.
RATE_LIMIT_STATE_ATTR = 'publicapi_rate_limit'


class ApiKeyRateThrottle(SimpleRateThrottle):
    """Limite le débit ET le VOLUME par CLÉ d'API (jamais par IP) — NTAPI6.

    Deux bornes distinctes, toutes deux issues du plan de la société
    (``core.ApiUsagePlan``, FG398 — jamais une valeur codée en dur ici) :

    * le DÉBIT par minute (``quota_par_minute`` + ``quota_burst``), appliqué
      par la mécanique DRF de fenêtre glissante ci-dessous ;
    * le VOLUME jour/mois (``quota_par_jour`` / ``quota_par_mois``), vérifié
      via le sélecteur de fondation ``core.api_usage.quota_depasse``.

    Sans clé reconnue, on ne throttle pas ici (la requête sera de toute façon
    rejetée par l'auth/permission) et AUCUN appel n'est compté — une requête
    non authentifiée ne doit jamais consommer le quota d'une société.

    Sans plan enregistré pour la société (cas nominal aujourd'hui), le
    comportement reste EXACTEMENT l'historique : taux DRF du scope
    « publicapi », aucune borne de volume, aucun en-tête de quota.

    ``core`` est appelé par son module SÉLECTEUR (``core.api_usage``), jamais
    par ses models — le sens de dépendance fondation → satellite reste
    ``publicapi`` consomme ``core``.
    """
    scope = 'publicapi'

    def get_cache_key(self, request, view):
        api_key = getattr(request, 'auth', None)
        if not isinstance(api_key, ApiKey):
            return None  # non throttlé ici
        return self.cache_format % {'scope': self.scope, 'ident': api_key.pk}

    def allow_request(self, request, view):
        api_key = getattr(request, 'auth', None)
        if not isinstance(api_key, ApiKey):
            return super().allow_request(request, view)

        from core import api_usage

        # 1) Débit/minute — borne du plan si elle existe, sinon le taux DRF.
        limite_minute = _safe(api_usage.limite_par_minute, api_key)
        if limite_minute:
            self.rate = f'{limite_minute}/minute'
            self.num_requests, self.duration = limite_minute, 60

        # 2) Volume jour/mois — l'état sert AUSSI aux en-têtes, y compris quand
        # la requête passe (« les en-têtes reflètent le compteur réel »).
        etat = _safe(api_usage.etat_quota, api_key)
        depasse = _safe(api_usage.quota_depasse, api_key) or False

        if depasse:
            # 429 + Retry-After = temps restant jusqu'à la réinitialisation de
            # la fenêtre de volume (jamais la fenêtre de débit, qui n'est pas
            # celle qui bloque).
            self._quota_wait = (etat or {}).get('retry_after') or 60
            _poser_etat(request, etat, depasse=True,
                        retry_after=self._quota_wait)
            # L'appel REFUSÉ est tout de même compté comme une erreur : sinon
            # un client en boucle sur un quota dépassé n'apparaîtrait nulle
            # part dans l'analytics d'usage de sa société.
            _safe(api_usage.record_call, api_key, erreur=True)
            return False

        autorise = super().allow_request(request, view)
        if autorise:
            _safe(api_usage.record_call, api_key)
            # Le compteur vient d'être incrémenté : refléter l'appel COURANT
            # dans `remaining` plutôt que l'état lu juste avant (sinon le
            # dernier appel autorisé annonce « il en reste 1 »).
            if etat:
                etat = dict(etat)
                etat['remaining'] = max(0, etat['remaining'] - 1)
            _poser_etat(request, etat, depasse=False, retry_after=None)
        else:
            # Refus de DÉBIT (fenêtre minute) : Retry-After vient de DRF.
            _poser_etat(request, etat, depasse=True,
                        retry_after=int(super().wait() or 1))
        return autorise

    def wait(self):
        """Secondes à attendre — la fenêtre de VOLUME prime quand c'est elle
        qui a bloqué (DRF ne connaît que sa fenêtre glissante de débit)."""
        quota_wait = getattr(self, '_quota_wait', None)
        if quota_wait:
            return quota_wait
        return super().wait()


def _safe(fonction, *args, **kwargs):
    """Appelle un sélecteur de quota sans jamais faire échouer la requête.

    Le comptage d'usage est une COURTOISIE d'observabilité : une base
    indisponible sur la table de compteurs ne doit pas transformer un GET
    parfaitement légitime en 500 (et surtout pas fermer l'API publique)."""
    try:
        return fonction(*args, **kwargs)
    except Exception:  # noqa: BLE001 — jamais bloquant
        import logging
        logging.getLogger(__name__).exception(
            'Quota API : %s a échoué (requête laissée passer)',
            getattr(fonction, '__name__', fonction))
        return None


def _poser_etat(request, etat, *, depasse, retry_after):
    """Mémorise l'état de quota sur la requête pour les en-têtes de réponse.

    ``request`` est la ``Request`` DRF ; l'attribut est posé sur l'objet
    ``HttpRequest` sous-jacent quand il existe, pour rester lisible depuis
    ``finalize_response`` quelle que soit l'enveloppe utilisée."""
    charge = {
        'etat': etat,
        'depasse': depasse,
        'retry_after': retry_after,
    }
    setattr(request, RATE_LIMIT_STATE_ATTR, charge)
    sous_jacent = getattr(request, '_request', None)
    if sous_jacent is not None:
        setattr(sous_jacent, RATE_LIMIT_STATE_ATTR, charge)


class ApiKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    """YAPIC6 — décrit `ApiKeyAuthentication` dans le schéma OpenAPI.

    Même raison que `CookieJWTAuthenticationScheme` (authentication/
    cookie_auth.py) : sans extension, drf-spectacular émet « could not resolve
    authenticator » sur chaque vue publique et n'expose aucun `securitySchemes`.
    Définie dans ce module pour être enregistrée dès que l'authenticator est
    chargé.
    """

    target_class = 'apps.publicapi.auth.ApiKeyAuthentication'
    name = 'publicApiKey'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': f'En-tête `Authorization: {AUTH_KEYWORD} <clé>`.',
        }


class QueryTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    """NTAPI30 — décrit `QueryTokenAuthentication` (même raison que
    `ApiKeyAuthenticationScheme` ci-dessus) : sans extension, drf-spectacular
    émet « could not resolve authenticator » sur `PublicCsvPullExportView`."""

    target_class = 'apps.publicapi.auth.QueryTokenAuthentication'
    name = 'publicApiQueryToken'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'query',
            'name': 'token',
            'description': (
                'Clé API en clair (scope lecture seule) — paramètre '
                '`?token=<clé>`, jamais un en-tête (endpoints pull sans '
                'en-tête custom possible, ex. `=IMPORTDATA()`).'),
        }
