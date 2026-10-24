"""YAPIC1 — pagination partagée avec plafond dur (``max_page_size``).

Le défaut historique pointait le ``PageNumberPagination`` brut de DRF :
``PAGE_SIZE=100`` figé, aucun ``page_size_query_param`` — un client ne pouvait
ni réduire la taille de page, ni le serveur borner une requête custom. Rien ne
garantissait non plus qu'un futur override ne renvoie une liste non bornée.

``StandardPagination`` :
  * ``page_size=50`` par défaut ;
  * ``page_size_query_param='page_size'`` — le client peut demander moins ;
  * ``max_page_size=200`` — PLAFOND DUR : ``?page_size=5000`` renvoie au plus
    200 lignes (DRF ``get_page_size`` borne à ``max_page_size``).

L'enveloppe ``count/next/previous/results`` reste STRICTEMENT identique à celle
de DRF (aucune surcharge de ``get_paginated_response``). Câblée en
``DEFAULT_PAGINATION_CLASS`` ; les 7 vues ``pagination_class=None`` volontaires
(dashboard core, connecteurs…) restent inchangées.
"""
import base64
import json
import re

from rest_framework.exceptions import ValidationError
from rest_framework.pagination import BasePagination, PageNumberPagination
from rest_framework.response import Response

import logging

logger = logging.getLogger(__name__)

# ERR-ENF11-FUZZ-PAGE-SIZE (11/10/2026) — le schéma OpenAPI (drf-spectacular)
# déclare ``page`` et ``page_size`` comme UN entier. DRF avalait en silence
# toute autre forme (``?page_size=null``, ``?page_size=abc``, paramètre
# répété…) et renvoyait 200 avec la taille par défaut : 295 constats api-fuzz
# « API accepted schema-violating request » sur toutes les listes paginées.
# Désormais une valeur non entière ou répétée → 400 ``validation_error``
# (déjà documenté sur chaque opération par ``core.openapi_erreurs``).
# Un entier conforme au schéma reste accepté tel qu'avant : ``0`` ou un
# négatif → taille par défaut, au-delà du plafond → ``max_page_size``.
_ENTIER = re.compile(r'^[+-]?\d+$')


def valider_parametre_entier(request, nom):
    """Lève 400 si le paramètre de requête ``nom`` est répété ou non entier.

    Absent → rien (le défaut s'applique). Renvoie la valeur brute sinon.
    """
    valeurs = request.query_params.getlist(nom)
    if not valeurs:
        return None
    if len(valeurs) > 1:
        raise ValidationError(
            {nom: [f"Le paramètre « {nom} » ne doit figurer qu'une fois."]})
    brut = valeurs[0]
    if not _ENTIER.match(brut):
        raise ValidationError(
            {nom: [f'Le paramètre « {nom} » doit être un nombre entier.']})
    return brut


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

    def get_page_size(self, request):
        brut = valider_parametre_entier(request, self.page_size_query_param)
        # api-fuzz-full 24/10/2026 — `?page_size=-26596` était accepté (taille par
        # défaut) alors que le schéma publie désormais `minimum: 1`.
        if brut is not None and int(brut) < 1:
            raise ValidationError({self.page_size_query_param: [
                f'Le paramètre « {self.page_size_query_param} » doit être au moins 1.']})
        return super().get_page_size(request)

    def get_schema_operation_parameters(self, view):
        # Publie `minimum: 1` sur page et page_size (ce que le serveur applique).
        params = super().get_schema_operation_parameters(view)
        for p in params:
            if p.get('name') in (self.page_query_param, self.page_size_query_param):
                p.setdefault('schema', {})['minimum'] = 1
        return params

    def paginate_queryset(self, queryset, request, view=None):
        # ``page`` répété ou NON ENTIER → 400 (nocturne 24/10/2026, api-fuzz-full :
        # 205 constats « accepted schema-violating » — DRF lit ``?page=`` vide
        # comme la page 1 alors que le schéma publie un entier). Un entier hors
        # plage garde le 404 « Page non valide » de DRF.
        valider_parametre_entier(request, self.page_query_param)
        return super().paginate_queryset(queryset, request, view)


# ---------------------------------------------------------------------------
# NTPLT14 — Pagination KEYSET pour les tables à forte croissance (étend YAPIC1).
#
# ``PageNumberPagination`` s'écroule sur les journaux à des millions de lignes :
# ``COUNT(*)`` scanne toute la table et ``OFFSET N`` relit N lignes pour rendre
# la page N. ``KeysetPagination`` pagine sur un CURSEUR opaque ``(created_at,
# id)`` — stable sous insertions concurrentes, AUCUN ``COUNT`` ni ``OFFSET``.
#
# OPT-IN & rétrocompatible : sans ``?cursor=`` la première page est renvoyée
# normalement + un ``next_cursor`` ; les clients page-number existants qui
# n'utilisent pas ce paginateur ne sont pas touchés. La réponse ajoute
# ``next_cursor`` sans casser l'enveloppe ``results``.
# ---------------------------------------------------------------------------


def _encode_cursor(created_at, pk) -> str:
    """Encode ``(created_at, id)`` en curseur base64 opaque et url-safe."""
    payload = json.dumps(
        {'ca': created_at.isoformat() if created_at else None, 'id': pk})
    raw = base64.urlsafe_b64encode(payload.encode('utf-8'))
    return raw.decode('ascii')


def _decode_cursor(cursor: str):
    """Décode un curseur → ``(created_at_iso, id)`` ou ``None`` si invalide."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode('ascii'))
        data = json.loads(raw.decode('utf-8'))
        return data.get('ca'), data.get('id')
    except Exception:  # noqa: BLE001 — curseur corrompu → ignoré (1re page) (D-ENF22-BLE001)
        logger.warning("decode cursor : échec ignoré, comportement dégradé", exc_info=True)
        return None


class KeysetPagination(BasePagination):
    """Pagination keyset sur ``(created_at, id)`` décroissants.

    Ordre : plus récent d'abord (``-created_at, -id``). Le curseur pointe la
    DERNIÈRE ligne de la page courante ; la page suivante prend les lignes
    STRICTEMENT plus anciennes. Aucun ``COUNT(*)`` (pas de ``count`` dans la
    réponse) ni ``OFFSET``. Stable sous insertions : une ligne insérée pendant
    la pagination n'introduit ni saut ni doublon.

    Usage : ``pagination_class = KeysetPagination`` sur un viewset dont le
    modèle a ``created_at`` + ``id`` (tout ``TenantModel``/``TimestampedModel``).
    """

    page_size = 50
    max_page_size = 200
    cursor_query_param = 'cursor'
    page_size_query_param = 'page_size'

    def _get_page_size(self, request):
        raw = valider_parametre_entier(request, self.page_size_query_param)
        if raw is not None:
            return max(1, min(int(raw), self.max_page_size))
        return self.page_size

    def paginate_queryset(self, queryset, request, view=None):
        self.page_size_effective = self._get_page_size(request)
        queryset = queryset.order_by('-created_at', '-id')
        cursor = request.query_params.get(self.cursor_query_param)
        if cursor:
            decoded = _decode_cursor(cursor)
            if decoded:
                created_at_iso, last_id = decoded
                # Lignes strictement plus anciennes que le curseur (keyset) :
                # created_at < ca, OU (created_at == ca ET id < last_id).
                from django.db.models import Q
                queryset = queryset.filter(
                    Q(created_at__lt=created_at_iso)
                    | Q(created_at=created_at_iso, id__lt=last_id))
        # On lit page_size + 1 pour savoir s'il reste une page suivante.
        window = list(queryset[:self.page_size_effective + 1])
        self._has_next = len(window) > self.page_size_effective
        page = window[:self.page_size_effective]
        self._next_cursor = None
        if self._has_next and page:
            last = page[-1]
            self._next_cursor = _encode_cursor(
                getattr(last, 'created_at', None), last.pk)
        return page

    def get_paginated_response(self, data):
        return Response({
            'results': data,
            'next_cursor': self._next_cursor,
            'has_next': self._has_next,
        })
