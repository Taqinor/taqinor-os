"""ENFP (décision fondateur D1 du 09/10/2026) — un paramètre de requête NON
DÉCLARÉ est REFUSÉ côté serveur (400 nommant le paramètre).

Constat (api-fuzz du 09/10, cluster D1, 302 constats « API accepted
schema-violating request ») : DRF ignore silencieusement tout ``?inconnu=…``.
Le contrat publié (OpenAPI) dit « ce paramètre n'existe pas » et le serveur
répond 200 : un client qui se trompe de nom de filtre (``?statut=`` au lieu de
``?status=``) reçoit la liste NON filtrée sans le savoir. Le fondateur a tranché :
refuser côté serveur, jamais filtrer ce constat dans ``schemathesis.toml``.

Mécanique (une seule source de vérité : le générateur OpenAPI lui-même)
---------------------------------------------------------------------
* L'ensemble AUTORISÉ d'une opération = exactement les paramètres ``in: query``
  que drf-spectacular déclarerait pour elle : ``@extend_schema(parameters=…)``,
  champs django-filter, ``search``/``ordering`` des filtres DRF (seulement sur
  une vue de liste, comme le schéma), paramètres de la pagination, ``format``
  quand plusieurs rendus existent. On appelle ``AutoSchema._get_parameters()``
  sur une vue jetable construite comme le fait le générateur
  (``SchemaGenerator.create_view``) : documenté == accepté, par construction —
  aucune liste parallèle à maintenir.
* + ``PARAMETRES_PLATEFORME`` : ``format`` seulement. DRF honore
  ``?format=`` (``URL_FORMAT_OVERRIDE``) sur TOUTE vue, que le schéma le
  déclare ou non ; une valeur inconnue y est déjà refusée (404 de négociation).
  Aucun paramètre global du frontend n'existe (vérifié 09/10 :
  ``frontend/src/api/axios.js`` ne pose que ``?entite=`` sur 4 listes, que leurs
  lanes déclarent) — pas de ``_`` anti-cache, pas de ``lang``.
* Calculé UNE fois par (classe de vue, action, méthode) puis mis en cache
  (``_CACHE``) : le coût par requête est une lecture de dict + une différence
  d'ensembles.
* Accroché UNE fois pour toutes les vues DRF : ``installer()`` (appelé par
  ``core.apps.CoreConfig.ready``) enveloppe ``APIView.initial`` — le contrôle
  tourne APRÈS authentification, permissions et débit (un anonyme reçoit
  toujours son 401, jamais un 400 qui renseignerait sur la route). Toute vue
  DRF est couverte, qu'elle hérite de ``TenantMixin`` ou non (vues publiques à
  jeton comprises : elles sont dans le schéma, le fuzz les frappe).

Hors périmètre, documenté
-------------------------
* Vue Django NON-DRF : aucun contrat OpenAPI → aucun contrôle.
* Vue DRF hors schéma (``schema = None``, ``@extend_schema(exclude=True)``,
  classe de schéma non drf-spectacular) : aucun contrat → aucun contrôle.
* ``OPTIONS`` (métadonnées, absentes du schéma) : aucun contrôle ; ``HEAD``
  suit ``GET``.
* Échec du calcul (``get_queryset`` exotique…) : on n'invente pas de refus —
  le contrôle est sauté pour cette opération et un avertissement est journalisé
  (une fois, le résultat ``None`` est mis en cache).

Réglage ``API_QUERY_PARAMS_STRICT`` (lu à chaque requête, donc
``override_settings`` fonctionne) : vrai en tests/CI et dans l'environnement du
fuzz (``settings.dev``), faux en production tant que les 8 lanes par app n'ont
pas déclaré tous leurs paramètres (``settings.prod``).

``core`` reste FONDATION : aucun import d'app domaine.
"""
from __future__ import annotations

import functools
import logging

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)

# Paramètres acceptés sur TOUTE vue DRF, déclarés ou non par le schéma (voir
# le docstring : ``format`` est honoré nativement par DRF partout).
PARAMETRES_PLATEFORME = frozenset({'format'})

MESSAGE_CHAMP = "Paramètre de requête non déclaré pour cette opération."

# (classe de vue, action, MÉTHODE) -> frozenset des noms autorisés, ou None
# (pas de contrat : contrôle sauté).
_CACHE: dict = {}


class ParametresRequeteInconnus(APIException):
    """400 ``unknown_query_parameter`` — ``parametres`` (triés) nomment les
    paramètres refusés ; ``core.exceptions`` les reprend dans ``fields``."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Paramètre de requête non déclaré.'
    default_code = 'unknown_query_parameter'

    def __init__(self, parametres):
        self.parametres = sorted(parametres)
        noms = ', '.join(self.parametres)
        pluriel = 's' if len(self.parametres) > 1 else ''
        super().__init__(
            detail=(f'Paramètre{pluriel} de requête non déclaré{pluriel} '
                    f'pour cette opération : {noms}.'),
            code=self.default_code)


def strict_actif() -> bool:
    return bool(getattr(settings, 'API_QUERY_PARAMS_STRICT', False))


class _RappelReconstitue:
    """Équivalent minimal du callback ``as_view()`` quand la requête n'a pas
    été résolue par l'URLconf (vue appelée directement, ex. APIRequestFactory)."""

    def __init__(self, view):
        self.cls = type(view)
        self.actions = getattr(view, 'action_map', None)
        self.initkwargs = {
            cle: getattr(view, cle) for cle in ('basename', 'detail', 'suffix')
            if cle in getattr(view, '__dict__', {})
        }


def _rappel(view, request):
    django_request = getattr(request, '_request', request)
    match = getattr(django_request, 'resolver_match', None)
    func = getattr(match, 'func', None)
    if func is not None and getattr(func, 'cls', None) is type(view):
        return func
    return _RappelReconstitue(view)


def _noms_query(parametres) -> set:
    """Noms de clés de query string couverts par les paramètres OpenAPI
    ``in: query`` (un objet ``form``/``explode`` se déplie en ses propriétés)."""
    noms = set()
    for param in parametres:
        if param.get('in') != 'query':
            continue
        nom = param.get('name')
        if nom:
            noms.add(nom)
        schema = param.get('schema') or {}
        if schema.get('type') == 'object' and param.get('explode', True):
            noms.update((schema.get('properties') or {}).keys())
    return noms


def _calculer(view, request, methode):
    from drf_spectacular.drainage import GENERATOR_STATS
    from drf_spectacular.generators import SchemaGenerator
    from drf_spectacular.openapi import AutoSchema
    from drf_spectacular.plumbing import ComponentRegistry
    from drf_spectacular.settings import spectacular_settings

    if getattr(type(view), 'schema', None) is None:
        return None
    chemin = getattr(getattr(request, '_request', request), 'path', '/')
    with GENERATOR_STATS.silence():
        vue = SchemaGenerator().create_view(_rappel(view, request), methode)
        schema = getattr(vue, 'schema', None)
        if not isinstance(schema, AutoSchema):
            return None
        vue.request = spectacular_settings.GET_MOCK_REQUEST(
            methode, chemin, vue, request)
        schema.registry = ComponentRegistry()
        # Chemin CONCRET (aucune variable ``{…}``) : seuls les paramètres de
        # chemin en dépendent, et on ne retient que ``in: query``.
        schema.path = chemin
        schema.path_regex = ''
        schema.path_prefix = ''
        schema.method = methode
        if schema.is_excluded():
            return None
        parametres = schema._get_parameters()
    return frozenset(_noms_query(parametres) | PARAMETRES_PLATEFORME)


def parametres_autorises(view, request):
    """Ensemble des noms de query autorisés pour l'opération en cours, ou
    ``None`` quand elle n'a pas de contrat OpenAPI (contrôle sauté)."""
    methode = request.method.upper()
    if methode == 'HEAD':
        methode = 'GET'
    action_map = getattr(view, 'action_map', None) or {}
    action = action_map.get(methode.lower()) if action_map else None
    cle = (type(view), action, methode)
    try:
        return _CACHE[cle]
    except KeyError:
        pass
    try:
        autorises = _calculer(view, request, methode)
    except Exception:  # pragma: no cover — journalisé, jamais un faux refus
        logger.warning(
            'API_QUERY_PARAMS_STRICT : paramètres non calculables pour %s.%s '
            '(%s) — contrôle sauté pour cette opération.',
            type(view).__module__, type(view).__qualname__, methode,
            exc_info=True)
        autorises = None
    _CACHE[cle] = autorises
    return autorises


def verifier_parametres_requete(view, request) -> None:
    """Lève ``ParametresRequeteInconnus`` si la query string porte une clé que
    l'opération ne déclare pas. No-op quand ``API_QUERY_PARAMS_STRICT`` est
    faux, sur ``OPTIONS`` et sans query string."""
    if not strict_actif() or request.method.upper() == 'OPTIONS':
        return
    cles = set(request.query_params.keys())
    if not cles:
        return
    autorises = parametres_autorises(view, request)
    if autorises is None:
        return
    inconnus = {
        cle for cle in cles - autorises
        # style ``deepObject`` : ``filtre[champ]=…`` relève de ``filtre``.
        if cle.split('[', 1)[0] not in autorises
    }
    if inconnus:
        raise ParametresRequeteInconnus(inconnus)


def vider_cache() -> None:
    _CACHE.clear()


def installer() -> None:
    """Enveloppe ``APIView.initial`` une seule fois (idempotent)."""
    from rest_framework.views import APIView

    origine = APIView.initial
    if getattr(origine, '_enfp_parametres_requete', False):
        return

    @functools.wraps(origine)
    def initial(self, request, *args, **kwargs):
        origine(self, request, *args, **kwargs)
        verifier_parametres_requete(self, request)

    initial._enfp_parametres_requete = True
    APIView.initial = initial
