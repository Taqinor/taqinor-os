"""Mixin de réponse COMMUN à toute vue de l'API publique (/api/public/v1/).

Appliqué aux deux bases de vue existantes (``PublicReadOnlyViewSet`` en
lecture, ``PublicWriteAPIView`` en écriture) — jamais dupliqué par vue :

* NTAPI3 — ``get_exception_handler()`` dédié (enveloppe d'erreur Stripe-like,
  voir ``errors.py``), au lieu du handler global YAPIC3
  (``core.exceptions.taqinor_exception_handler``, qui reste inchangé pour
  ``/api/django/``, ``/api/v1/``…).
* NTAPI5 — pose TOUJOURS l'en-tête ``X-Taqinor-Api-Version`` (épinglé par
  clé, ``ApiKey.api_version``, défaut ``'v1'``) sur TOUTE réponse (succès ou
  erreur) — la version SERVIE dépend de la clé, jamais du path appelé.
* NTAPI1 — mémorise en plus la version DEMANDÉE par l'appel
  (``request.public_api_version``, lue du chemin puis de l'en-tête de requête).
  Les deux notions restent distinctes : « ce que le client croit appeler »
  (demandée) vs « ce que le serveur sert » (épinglée par clé). NTAPI2 cible ses
  annonces de dépréciation sur la première.
"""
from .auth import RATE_LIMIT_STATE_ATTR
from .deprecation import ApiDeprecationHeadersMixin
from .errors import public_api_exception_handler
from .versioning import version_demandee

# NTAPI6 — en-têtes de quota standards, posés sur CHAQUE réponse publique dès
# qu'un plan borne le volume de la société (sans plan : aucun en-tête, contrat
# historique inchangé).
RATE_LIMIT_LIMIT_HEADER = 'X-RateLimit-Limit'
RATE_LIMIT_REMAINING_HEADER = 'X-RateLimit-Remaining'
RATE_LIMIT_RESET_HEADER = 'X-RateLimit-Reset'
RETRY_AFTER_HEADER = 'Retry-After'

# NTAPI5 — en-tête de version épinglée par clé.
API_VERSION_HEADER = 'X-Taqinor-Api-Version'
# Version servie par défaut si la clé n'a pas encore de `api_version` posé
# (ne devrait pas arriver après la migration NTAPI5) ou si `request.auth`
# n'est pas encore résolu (ex. 401 avant authentification).
DEFAULT_API_VERSION = 'v1'


class PublicApiResponseMixin(ApiDeprecationHeadersMixin):
    """À placer EN PREMIER dans le MRO (avant la base DRF) sur toute vue
    montée sous ``/api/public/v1/``."""

    def get_exception_handler(self):
        return public_api_exception_handler

    def initial(self, request, *args, **kwargs):
        # NTAPI1 — résolu AVANT l'authentification/permissions pour être
        # disponible même sur un rejet (401/403) : la version demandée ne
        # dépend jamais de la clé.
        request.public_api_version = version_demandee(request)
        return super().initial(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        api_key = getattr(request, 'auth', None)
        version = getattr(api_key, 'api_version', None) or DEFAULT_API_VERSION
        response[API_VERSION_HEADER] = version
        # NTAPI23 — une clé en grace period de rotation (``expire_le`` posé,
        # encore valide) porte un en-tête ``Deprecation`` sur CHAQUE appel,
        # pour que l'intégration cliente sache migrer avant l'échéance.
        expire_le = getattr(api_key, 'expire_le', None)
        if expire_le:
            response['Deprecation'] = expire_le.isoformat()
        # NTAPI6 — en-têtes de quota, reflet du COMPTEUR RÉEL de la société.
        self._poser_entetes_quota(request, response)
        # NTAPI2 — annonce de dépréciation de L'ENDPOINT (RFC 8594). Posée
        # APRÈS NTAPI23 : quand les deux s'appliquent, l'annonce d'endpoint
        # gagne (signal le plus fort, seul format conforme à la RFC). Sans
        # annonce, rien n'est touché — comportement historique inchangé.
        response = self.poser_entetes_deprecation(request, response)
        return response

    def _poser_entetes_quota(self, request, response):
        """NTAPI6 — `X-RateLimit-Limit/Remaining/Reset` (+ `Retry-After` sur
        429) depuis l'état mémorisé par `ApiKeyRateThrottle`.

        Aucun en-tête quand aucune borne de VOLUME ne s'applique : inventer un
        « quota » là où le plan n'en fixe aucun tromperait le client sur une
        limite qui n'existe pas. `Retry-After` n'est écrasé que si DRF ne l'a
        pas déjà posé (il le fait sur un refus de DÉBIT — sa valeur est alors
        la bonne)."""
        charge = getattr(request, RATE_LIMIT_STATE_ATTR, None)
        if not charge:
            return response
        etat = charge.get('etat')
        if etat:
            response[RATE_LIMIT_LIMIT_HEADER] = str(etat['limit'])
            response[RATE_LIMIT_REMAINING_HEADER] = str(etat['remaining'])
            response[RATE_LIMIT_RESET_HEADER] = str(etat['reset'])
        retry_after = charge.get('retry_after')
        if (charge.get('depasse') and retry_after
                and RETRY_AFTER_HEADER not in response):
            response[RETRY_AFTER_HEADER] = str(int(retry_after))
        return response
