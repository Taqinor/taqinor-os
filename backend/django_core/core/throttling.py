"""NTPLT42 — throttle applicatif PAR TENANT (étend YAPIC12).

``TenantRateThrottle`` borne le débit de requêtes PAR SOCIÉTÉ : le script fou
d'UN client (une boucle qui martèle l'API) ne peut plus dégrader l'instance
partagée pour les AUTRES sociétés. Posé en ``DEFAULT_THROTTLE_CLASSES``, il
s'applique à toutes les vues DRF.

Budget : ``DEFAULT_THROTTLE_RATES['tenant']`` (settings, piloté par l'env
``TENANT_RATE_LIMIT``, défaut GÉNÉREUX ``1200/min``). ``0`` / valeur vide =
throttle DÉSACTIVÉ (``rate=None`` → ``allow_request`` laisse tout passer),
comportement historique.

Portée du compteur : la CLÉ de cache est la société (``company`` de l'appelant).
Une requête sans société résolue (anonyme, /token/, /register/, superuser sans
company) N'EST PAS throttlée par tenant (``get_cache_key`` renvoie ``None``) —
ces surfaces gardent leurs throttles dédiés (login/register par IP). Le 429
émis est l'exception DRF standard, donc uniformisé par l'enveloppe YAPIC12.
"""
from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle

#: Longueur maximale retenue d'une adresse lue dans un en-tête (une IPv6 en
#: fait 45 ; au-delà, l'en-tête ne décrit plus une adresse).
MAX_LONGUEUR_IP = 64


def _texte_ip(valeur) -> str:
    if valeur is None:
        return ''
    try:
        return str(valeur).strip()[:MAX_LONGUEUR_IP]
    except Exception:  # noqa: BLE001 — défensif : une IP illisible vaut ''
        return ''


def ip_de_requete(request) -> str:
    """QJR416 — LA SEULE lecture d'adresse IP du dépôt, et elle lit le
    **dernier saut de confiance**.

    LE DÉFAUT QUE CECI FERME (trois symptômes, une racine).

    * ``ventes/public_views._client_ip`` prenait le **PREMIER** saut de
      ``X-Forwarded-For`` — une valeur **choisie par l'appelant** — et c'est le
      champ de PREUVE du registre immuable de signature électronique
      (loi 53-05) : n'importe qui pouvait donc écrire l'IP qui serait opposée à
      un signataire.
    * les throttles publics héritaient du ``get_ident`` de DRF, lui aussi assis
      sur le premier saut quand ``NUM_PROXIES`` est absent (il l'est) : le seau
      de limitation était **adressable par l'appelant**, donc contournable.
    * ``crm/public_views._hash_ip`` hachait ``REMOTE_ADDR`` : derrière le proxy,
      la valeur est **constante pour tous les visiteurs** et le journal de
      consultation ne distinguait plus personne (QJR4-11, requalifié
      « qualité de données »).

    LA RÈGLE, ET IL N'Y EN A QU'UNE : on lit le dernier saut que NOTRE
    infrastructure a réellement observé.

    1. ``X-Forwarded-For`` — nginx **APPEND** à cette chaîne : le DERNIER saut
       est donc l'adresse que notre propre proxy a vue, la seule que l'appelant
       ne peut pas forger. ``NUM_PROXIES`` (même nom et même sémantique que
       DRF) déclare combien de proxies À NOUS ajoutent leur entrée : on saute
       ces ``n`` derniers pour retrouver le visiteur. Absent ⇒ dernier saut.
    2. ``CF-Connecting-IP`` — une seule adresse, posée par Cloudflare. Elle est
       DÉCLARATIVE comme les autres : elle n'est honorée que si le déploiement
       déclare Cloudflare comme proxy de confiance
       (``CF_CONNECTING_IP_TRUSTED``), jamais par défaut.
    3. ``REMOTE_ADDR`` — le pair TCP direct, dernier recours.

    Ne lève jamais : une lecture impossible rend ``''`` (l'appelant omet, il
    n'invente pas).
    """
    if request is None:
        return ''
    try:
        from django.conf import settings

        meta = getattr(request, 'META', None) or {}
        transmise = _texte_ip(meta.get('HTTP_X_FORWARDED_FOR'))
        if transmise:
            sauts = [s for s in (_texte_ip(x)
                                 for x in str(transmise).split(',')) if s]
            if sauts:
                # ``NUM_PROXIES`` se lit au niveau Django OU dans le bloc
                # ``REST_FRAMEWORK`` (où DRF le range) : les deux emplacements
                # sont honorés, un seul réglage à poser au deploy.
                nb_proxies = getattr(settings, 'NUM_PROXIES', None)
                if nb_proxies is None:
                    nb_proxies = (
                        getattr(settings, 'REST_FRAMEWORK', None)
                        or {}).get('NUM_PROXIES')
                try:
                    nb_proxies = int(nb_proxies)
                except (TypeError, ValueError):
                    nb_proxies = 0
                nb_proxies = max(0, nb_proxies)
                indice = len(sauts) - 1 - nb_proxies
                # Une chaîne plus courte que le nombre de proxies déclarés est
                # une chaîne TRONQUÉE (ou forgée) : on garde le saut le plus à
                # gauche disponible plutôt que de sortir du tableau.
                return sauts[max(0, indice)]
        if getattr(settings, 'CF_CONNECTING_IP_TRUSTED', False):
            cloudflare = _texte_ip(meta.get('HTTP_CF_CONNECTING_IP'))
            if cloudflare:
                return cloudflare
        return _texte_ip(meta.get('REMOTE_ADDR'))
    except Exception:  # noqa: BLE001 — défensif
        return ''


class IdentIpPartageeMixin:
    """QJR416 — ``get_ident`` assis sur :func:`ip_de_requete`.

    DRF calcule son identifiant de seau à partir du PREMIER saut de
    ``X-Forwarded-For`` dès que ``NUM_PROXIES`` est absent (il l'est) : le seau
    devenait adressable par l'appelant, donc la limite contournable en changeant
    un en-tête. Ce mixin lui substitue LA primitive partagée — une seule lecture
    d'IP dans le dépôt. Repli sur le comportement DRF si la primitive ne sait
    rien lire (jamais un seau vide partagé par tout le monde).
    """

    def get_ident(self, request):
        ident = ip_de_requete(request)
        if ident:
            return ident
        return super().get_ident(request)


class TenantRateThrottle(SimpleRateThrottle):
    """Débit par société (clé de cache = id de la company de l'appelant)."""

    scope = 'tenant'

    def get_cache_key(self, request, view):
        user = getattr(request, 'user', None)
        if user is None or not getattr(user, 'is_authenticated', False):
            return None  # anonyme → pas de throttle tenant (login/register gèrent)
        company = getattr(user, 'company', None)
        company_id = getattr(company, 'pk', None) if company is not None else None
        if company_id is None:
            return None  # superuser/opérateur sans société → non throttlé ici
        return f'throttle_tenant_{company_id}'
