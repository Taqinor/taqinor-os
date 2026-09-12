"""NTAPI2 — sélecteur des dépréciations d'API (RFC 8594).

Couche de FONDATION, exactement comme ``core.api_usage`` (FG398) : ``core``
porte la TABLE (``core.models.ApiDeprecation``) et la logique de RÉSOLUTION
« ce chemin est-il déprécié ? » ; l'app satellite ``publicapi`` la CONSOMME via
ce module (jamais l'inverse — contrat import-linter
``core-foundation-is-a-base-layer``). Aucune importation d'app métier ici.

Résolution
----------
``deprecation_pour(path, *, version=None, company_id=None, now=None)`` renvoie
l'annonce APPLICABLE la plus urgente (``sunset_at`` le plus proche) parmi :

* les annonces GLOBALES (``company`` NULL) ;
* les annonces CIBLÉES sur ``company_id``.

Une annonce s'applique quand elle est ``actif``, que sa ``version`` correspond
(ou est vide = toutes versions), et que ``endpoint_pattern`` (motif **glob**,
``fnmatch`` — jamais une regex, pour qu'une saisie admin ne puisse pas faire
exploser le temps de réponse) matche le chemin complet de la requête.

``deprecated_at`` dans le FUTUR ⇒ l'annonce n'est pas encore active : un
endpoint courant ne renvoie aucun en-tête (c'est exactement le second volet du
critère d'acceptation NTAPI2).
"""
from __future__ import annotations

from fnmatch import fnmatchcase

from django.db.models import Q
from django.utils import timezone

from .models import ApiDeprecation

# Cible par défaut de l'en-tête ``Link: <…>; rel="deprecation"`` quand
# l'annonce ne précise pas la sienne — la référence FR publique, servie par
# l'API elle-même (FG105). Chaîne littérale : ``core`` ne peut pas importer
# ``publicapi`` pour lire sa constante de base.
DEFAULT_DEPRECATION_DOC_URL = '/api/public/v1/openapi.json'


def _applies(annonce, path: str, version, now) -> bool:
    if annonce.deprecated_at and annonce.deprecated_at > now:
        return False  # annoncée pour plus tard : pas encore dépréciée
    if version and annonce.version and annonce.version != version:
        return False
    motif = annonce.endpoint_pattern or ''
    if not motif:
        return False
    return fnmatchcase(path, motif)


def deprecations_actives(*, version=None, company_id=None, now=None):
    """Toutes les annonces potentiellement applicables (globales + ciblées).

    Requête UNIQUE, bornée par ``actif`` et la version — le filtrage par motif
    de chemin se fait ensuite en Python (``fnmatch``), jamais en SQL (aucun
    ``LIKE`` construit depuis une saisie utilisateur).
    """
    now = now or timezone.now()
    qs = ApiDeprecation.objects.filter(actif=True)
    scope = Q(company__isnull=True)
    if company_id:
        scope |= Q(company_id=company_id)
    qs = qs.filter(scope)
    if version:
        qs = qs.filter(Q(version=version) | Q(version=''))
    return qs


def deprecation_pour(path, *, version=None, company_id=None, now=None):
    """Annonce applicable à ``path`` la plus URGENTE (sunset le plus proche),
    ou ``None``. Ne lève jamais : un motif malformé est simplement ignoré."""
    if not path:
        return None
    now = now or timezone.now()
    candidates = [
        annonce
        for annonce in deprecations_actives(
            version=version, company_id=company_id, now=now)
        if _applies(annonce, path, version, now)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda a: (a.sunset_at, a.pk))


def entetes_rfc8594(annonce):
    """Les trois en-têtes RFC 8594 d'une annonce, prêts à poser sur la réponse.

    ``Sunset`` suit la RFC 8594 : un **HTTP-date** (RFC 7231, IMF-fixdate) —
    jamais un ISO-8601, qu'un client conforme ne saurait pas lire.
    """
    from django.utils.http import http_date

    doc = annonce.doc_url or DEFAULT_DEPRECATION_DOC_URL
    return {
        'Deprecation': 'true',
        'Sunset': http_date(annonce.sunset_at.timestamp()),
        'Link': f'<{doc}>; rel="deprecation"',
    }
