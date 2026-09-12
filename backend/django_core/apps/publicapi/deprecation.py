"""NTAPI2 — mixin DRF posant les en-têtes de dépréciation RFC 8594.

Consomme le sélecteur de FONDATION ``core.api_deprecation`` (la table
``core.ApiDeprecation`` vit dans ``core``, jamais dans cette app) — même sens
de dépendance que ``core.api_usage`` (FG398) : ``publicapi`` appelle ``core``,
jamais l'inverse.

Ce mixin est fondu dans ``public_response.PublicApiResponseMixin``, la base
COMMUNE de toute vue montée sous ``/api/public/v1/`` : marquer un endpoint
déprécié ne demande donc AUCUNE modification de vue — il suffit de créer la
ligne ``ApiDeprecation`` correspondante (par société, ou globale).

Trois en-têtes, exactement ceux de la RFC 8594 :

* ``Deprecation: true`` ;
* ``Sunset: <HTTP-date>`` (IMF-fixdate, jamais un ISO-8601) ;
* ``Link: <doc>; rel="deprecation"``.

Un endpoint COURANT (aucune annonce applicable) n'en reçoit aucun — c'est le
second volet du critère d'acceptation, et c'est pour cela que le mixin ne pose
jamais de valeur « par défaut ».

Cohabitation avec NTAPI23 (rotation de clé). NTAPI23 pose déjà un en-tête
``Deprecation`` portant la fin de la période de grâce de LA CLÉ appelante.
Les deux signaux sont distincts (« ta clé expire » vs « cet endpoint
disparaît ») et ne peuvent pas partager la même valeur : quand une annonce
d'endpoint s'applique, elle GAGNE — c'est le signal le plus fort (l'endpoint
cessera de répondre pour tout le monde, pas seulement pour cette clé), et c'est
le seul des deux qui soit conforme à la RFC (``true`` + ``Sunset`` + ``Link``).
Sans annonce d'endpoint, le comportement NTAPI23 reste octet-identique.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ApiDeprecationHeadersMixin:
    """Pose les en-têtes RFC 8594 quand le chemin appelé est déprécié."""

    def poser_entetes_deprecation(self, request, response):
        """Best-effort : une erreur de résolution ne doit JAMAIS transformer
        une réponse 200 en 500 (les en-têtes sont une courtoisie, pas le
        contrat de la ressource)."""
        try:
            from core.api_deprecation import deprecation_pour, entetes_rfc8594

            api_key = getattr(request, 'auth', None)
            annonce = deprecation_pour(
                request.path,
                version=getattr(request, 'public_api_version', None),
                company_id=getattr(api_key, 'company_id', None),
            )
            if annonce is None:
                return response
            for nom, valeur in entetes_rfc8594(annonce).items():
                response[nom] = valeur
            if annonce.message:
                # En-tête d'explication FR — additif, hors RFC (qui ne prévoit
                # pas de champ « pourquoi »). Repli silencieux si le message
                # porte un caractère non latin-1 (les en-têtes HTTP ne
                # transportent pas d'UTF-8 brut) : jamais une exception.
                try:
                    response['X-Taqinor-Deprecation-Message'] = (
                        annonce.message[:300].encode('latin-1', 'replace')
                        .decode('latin-1'))
                except Exception:  # noqa: BLE001 — jamais bloquant
                    pass
        except Exception:  # noqa: BLE001 — jamais bloquant
            logger.exception('Résolution de dépréciation API échouée')
        return response
