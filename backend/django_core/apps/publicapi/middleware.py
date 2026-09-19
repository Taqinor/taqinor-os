"""NTAPI38 — middleware LÉGER de journalisation des appels de l'API publique.

Ne s'intéresse qu'aux chemins sous ``/api/public/`` ; tout le reste de l'ERP
traverse ce middleware sans une seule requête SQL supplémentaire (un simple
test de préfixe de chaîne, avant même de démarrer le chronomètre).

POURQUOI UN MIDDLEWARE ET NON UN MIXIN DE VUE. La latence qui intéresse un
admin tenant est celle que son intégration MESURE — enveloppe de réponse,
sérialisation et rendu compris —, pas seulement le temps passé dans le corps de
la vue. Et un 401 rejeté par l'authentification, ou un 404 qui n'atteint
aucune vue, doit lui aussi apparaître : c'est précisément ce qu'on regarde
quand une intégration « ne marche plus ». Seul un middleware voit les deux.

LA CLÉ D'API VIENT DE L'AUTHENTIFICATION, PAS D'UNE SECONDE RÉSOLUTION.
``auth.memoriser_cle`` dépose la ``ApiKey`` résolue sur la ``HttpRequest``
sous-jacente (même patron que l'état de quota NTAPI6, lu par
``public_response``) : le middleware la relit sans refaire ni requête ni
hachage, et une requête non authentifiée n'a simplement pas d'attribut.
"""
from __future__ import annotations

import time

from .auth import API_KEY_STATE_ATTR
from .constants import PUBLIC_API_LEGACY_BASE

# Préfixe surveillé : la racine NON versionnée, donc `/api/public/v1/...` ET
# l'alias legacy 301 sont couverts par le même test (jamais deux préfixes à
# tenir synchronisés quand une v2 apparaîtra).
PREFIXE_SURVEILLE = PUBLIC_API_LEGACY_BASE


class PublicApiCallLogMiddleware:
    """Journalise un ``ApiCallLog`` par appel sous ``/api/public/``."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(PREFIXE_SURVEILLE):
            return self.get_response(request)

        debut = time.monotonic()
        response = self.get_response(request)
        latence_ms = int((time.monotonic() - debut) * 1000)
        self._journaliser(request, response, latence_ms)
        return response

    def _journaliser(self, request, response, latence_ms):
        from . import call_log

        api_key = getattr(request, API_KEY_STATE_ATTR, None)
        company_id = getattr(api_key, 'company_id', None)
        if not company_id:
            # Appel non authentifié (401 sur clé absente/invalide) : aucune
            # société propriétaire, donc aucune ligne — l'inscrire exigerait
            # d'inventer un propriétaire, et un journal par société n'est pas
            # l'endroit où surveiller des tentatives anonymes.
            return
        call_log.enregistrer(
            company_id=company_id,
            api_key_id=getattr(api_key, 'pk', None),
            methode=request.method,
            # `request.path` NE PORTE PAS la query string : un `?token=` (pull
            # CSV NTAPI30) est une clé en clair, jamais recopiée en base.
            chemin=request.path,
            statut=response.status_code,
            latence_ms=latence_ms,
            request_id=getattr(request, 'request_id', '') or '',
            taille_payload=self._taille(response),
        )

    @staticmethod
    def _taille(response):
        """Octets du corps de réponse, sans jamais consommer un streaming.

        Une réponse en streaming n'expose pas sa taille avant d'être lue ; la
        lire ici la viderait pour le client. On rend 0 plutôt que de casser la
        réponse pour une statistique."""
        if getattr(response, 'streaming', False):
            return 0
        longueur = response.get('Content-Length')
        if longueur:
            try:
                return int(longueur)
            except (TypeError, ValueError):
                return 0
        try:
            return len(response.content)
        except Exception:  # noqa: BLE001 — statistique, jamais bloquante
            return 0
