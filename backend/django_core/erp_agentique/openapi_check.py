"""WOW-CI3 — générateur de schéma OpenAPI *pour le contrôle CI* : un seul
parcours d'introspection au lieu de deux, document final IDENTIQUE.

POURQUOI
--------
`erp_agentique/urls.py` monte la MÊME liste `_APP_URLS` sous DEUX préfixes :
``api/django/`` (historique) et ``api/v1/`` (YAPIC7). drf-spectacular ne le
sait pas : il ré-instancie chaque vue, ré-introspecte chaque serializer et
ré-résout chaque type-hint une SECONDE fois pour le miroir — 8 423 opérations
strictement dérivables des 8 467 premières. Mesuré dans l'image de prod :
``get_schema()`` = 284 s pour 16 918 opérations, dont ~142 s de pur doublon.

CE MODULE NE CHANGE AUCUNE ROUTE D'EXÉCUTION. Il n'est jamais importé par
``ROOT_URLCONF``, ni par un settings, ni par une vue : seul
``scripts/check_openapi_schema.py`` le désigne via
``manage.py spectacular --generator-class ...``. Le schéma servi en ligne
(``/api/schema/``) continue d'être produit par le générateur par défaut sur
l'URLconf complète.

COMMENT
-------
1. ``urlpatterns`` (plus bas) = l'URLconf racine PRIVÉE de son seul montage
   ``api/v1/``. Rien n'est recopié à la main : c'est la vraie liste racine
   filtrée, donc elle ne peut pas diverger.
2. ``SchemaGeneratorAliasV1.parse()`` appelle le ``parse()`` d'origine sur cet
   arbre réduit, puis RECONSTITUE le miroir ``api/v1/`` par copie profonde de
   chaque opération ``api/django/…`` issue de ``_APP_URLS``, avec le seul
   changement que drf-spectacular lui-même appliquerait : ``operationId``
   ``django_X`` -> ``v1_X`` (relation vérifiée sur les 8 423 opérations de
   l'instantané versionné, suffixes de collision ``_2`` compris).
3. L'expansion a lieu DANS ``parse()``, donc AVANT ``build_root_object()``,
   les POSTPROCESSING_HOOKS (nommage des énums), ``normalize_result_object``
   et ``sanitize_result_object`` : le miroir traverse exactement la même
   chaîne que les opérations réelles. Le document rendu — et donc l'inventaire
   de contrat ``docs/openapi-schema.yml`` — reste identique au bit près.

GARDE-FOUS (tout écart fait ÉCHOUER la génération, jamais passer en silence)
---------------------------------------------------------------------------
* exactement UN montage ``api/v1/`` à la racine, et sa cible est le MÊME objet
  Python que celle du montage ``api/django/`` (identité, pas égalité) ;
* aucune autre entrée racine sous ``api/v1/`` ;
* chaque opération ``api/django/…`` à recopier porte bien un ``operationId``
  préfixé ``django_`` — c'est la sonde qui détecte une dérive de l'estimation
  de préfixe commun de drf-spectacular (``os.path.commonpath``) ;
* et en dernier ressort, l'instantané versionné : s'il reste une différence,
  ``check_openapi_schema.py`` rougit. Le raccourci ne peut produire qu'un
  FAUX ROUGE, jamais un faux vert.
"""
from __future__ import annotations

import copy
import functools

from django.core.exceptions import ImproperlyConfigured
from django.urls import URLResolver
from drf_spectacular import drainage
from drf_spectacular.generators import SchemaGenerator

from erp_agentique import urls as _urls_racine

#: Préfixe d'URL du second montage (miroir versionné) — cf. urls.py, YAPIC7.
ROUTE_V1 = 'api/v1/'
#: Préfixe d'URL du montage historique.
ROUTE_INTERNE = 'api/django/'
#: Chemins tels qu'ils apparaissent dans le document OpenAPI.
CHEMIN_V1 = '/api/v1/'
CHEMIN_INTERNE = '/api/django/'
#: Préfixe d'operationId dérivé de `CHEMIN_INTERNE` par drf-spectacular.
OID_INTERNE = 'django_'
OID_V1 = 'v1_'
#: Étiquette auto-dérivée : drf-spectacular retire le préfixe commun estimé
#: (`/api`) et prend le premier segment restant — donc `django` d'un côté,
#: `v1` de l'autre. Une étiquette POSÉE À LA MAIN (`@extend_schema(tags=…)`)
#: ne vaut jamais l'un de ces deux mots, elle traverse donc inchangée.
TAG_INTERNE = 'django'
TAG_V1 = 'v1'

#: Ce module N'EST PAS l'URLconf d'exécution ; il ne sert qu'à ce contrôle.
_MODULE = 'erp_agentique.openapi_check'


def _route(entree) -> str | None:
    """Route littérale d'une entrée d'URLconf (None pour un ``re_path``)."""
    return getattr(entree.pattern, '_route', None)


def _monter_urlpatterns():
    """URLconf racine PRIVÉE du montage `api/v1/`, avec ses garde-fous."""
    racine = _urls_racine.urlpatterns
    montages_v1 = [e for e in racine if _route(e) == ROUTE_V1]
    autres_v1 = [e for e in racine
                 if _route(e) != ROUTE_V1 and (_route(e) or '').startswith(ROUTE_V1)]
    montages_interne = [e for e in racine if _route(e) == ROUTE_INTERNE]

    if len(montages_v1) != 1:
        raise ImproperlyConfigured(
            f"{_MODULE} : {len(montages_v1)} montage(s) '{ROUTE_V1}' a la racine "
            f"(1 attendu). Le raccourci de generation du schema suppose UN seul "
            f"miroir versionne — voir erp_agentique/urls.py (YAPIC7).")
    if autres_v1:
        raise ImproperlyConfigured(
            f"{_MODULE} : entree(s) racine supplementaire(s) sous '{ROUTE_V1}' "
            f"({[_route(e) for e in autres_v1]}). Elles ne seraient PAS "
            f"reconstituees par le miroir : monter la route dans _APP_URLS, ou "
            f"adapter ce module.")
    if len(montages_interne) != 1:
        raise ImproperlyConfigured(
            f"{_MODULE} : {len(montages_interne)} montage(s) '{ROUTE_INTERNE}' a "
            f"la racine (1 attendu).")

    mont_v1, mont_interne = montages_v1[0], montages_interne[0]
    if not isinstance(mont_v1, URLResolver) or not isinstance(mont_interne, URLResolver):
        raise ImproperlyConfigured(
            f"{_MODULE} : '{ROUTE_V1}' et '{ROUTE_INTERNE}' doivent etre des "
            f"include() (URLResolver).")
    if mont_v1.urlconf_name is not mont_interne.urlconf_name:
        raise ImproperlyConfigured(
            f"{_MODULE} : '{ROUTE_V1}' ne monte PAS le meme objet que "
            f"'{ROUTE_INTERNE}' — le miroir n'est donc plus derivable. "
            f"Regenerer le schema sans --generator-class, ou adapter ce module.")

    return [e for e in racine if e is not mont_v1]


def _prefixes_sans_jumeau_v1() -> tuple[str, ...]:
    """Chemins `api/django/…` montés HORS de `_APP_URLS` (donc sans miroir).

    Aujourd'hui : les routes publiques tokenisees (`api/django/public/…`), les
    trois endpoints JWT (`api/django/token/…`) et l'admin. Derive de l'URLconf,
    jamais ecrite en dur : une route ajoutee a la racine est prise en compte
    automatiquement.
    """
    prefixes = []
    for entree in _urls_racine.urlpatterns:
        route = _route(entree) or ''
        if route.startswith(ROUTE_INTERNE) and route != ROUTE_INTERNE:
            prefixes.append('/' + route)
    return tuple(sorted(set(prefixes)))


def a_un_jumeau_v1(chemin: str, prefixes_exclus) -> bool:
    """Vrai si `chemin` (document OpenAPI) est servi aussi sous `api/v1/`."""
    if not chemin.startswith(CHEMIN_INTERNE):
        return False
    return not any(chemin.startswith(p) for p in prefixes_exclus)


def etendre_miroir_v1(chemins: dict, prefixes_exclus) -> int:
    """Ajoute le miroir `api/v1/` de chaque opération `api/django/` éligible.

    Copie PROFONDE : le miroir doit pouvoir être muté par les
    POSTPROCESSING_HOOKS sans que la mutation retombe sur l'opération d'origine.
    """
    miroir = {}
    for chemin, item in chemins.items():
        if not a_un_jumeau_v1(chemin, prefixes_exclus):
            continue
        copie = {}
        for methode, operation in (item or {}).items():
            operation = copy.deepcopy(operation)
            if methode == 'parameters':
                # Clé de niveau CHEMIN (paramètres partagés), pas une méthode.
                # `parse()` n'en produit pas aujourd'hui ; la recopier telle
                # quelle reste le comportement juste si cela changeait.
                copie[methode] = operation
                continue
            oid = operation.get('operationId')
            if not isinstance(oid, str) or not oid.startswith(OID_INTERNE):
                raise ImproperlyConfigured(
                    f"{_MODULE} : l'operation {methode.upper()} {chemin} porte "
                    f"l'operationId {oid!r}, qui ne commence pas par "
                    f"'{OID_INTERNE}'. drf-spectacular a donc change son "
                    f"estimation de prefixe commun : le miroir v1 ne peut plus "
                    f"etre derive mecaniquement. Regenerer sans "
                    f"--generator-class et corriger ce module.")
            operation['operationId'] = OID_V1 + oid[len(OID_INTERNE):]
            etiquettes = operation.get('tags')
            if isinstance(etiquettes, list):
                operation['tags'] = [TAG_V1 if e == TAG_INTERNE else e
                                     for e in etiquettes]
            copie[methode] = operation
        miroir[CHEMIN_V1 + chemin[len(CHEMIN_INTERNE):]] = copie
    chemins.update(miroir)
    return len(miroir)


def elargir_cache_source_location() -> bool:
    """Déplafonne le cache de ``drainage._get_source_location`` (WOW-CI3).

    ``manage.py spectacular`` active ``enable_trace_lineno()``, donc chaque
    classe de vue/serializer rencontrée passe par ``inspect.getsourcelines()``
    — « a rather expensive operation », de l'aveu du commentaire amont, qui
    s'appuie sur un ``lru_cache(maxsize=1000)`` pour ne la payer qu'une fois
    par classe. Ce dépôt dépasse largement 1 000 classes distinctes : le cache
    EXPULSE en permanence et l'opération chère est repayée à chaque visite.

    Déplafonner le cache ne change RIEN au résultat (mêmes fichier et ligne
    pour les mêmes objets, donc journal d'avertissements identique) : cela
    supprime seulement le recalcul. Retourne True si le remplacement a eu lieu
    — si la structure amont change, on n'échoue pas : on garde le
    comportement d'origine.
    """
    fonction = getattr(drainage, '_get_source_location', None)
    origine = getattr(fonction, '__wrapped__', None)
    if origine is None or getattr(fonction, 'cache_info', None) is None:
        return False
    if fonction.cache_info().maxsize is None:
        return True  # déjà déplafonné (2e instanciation dans le même process)
    drainage._get_source_location = functools.lru_cache(maxsize=None)(origine)
    return True


class SchemaGeneratorAliasV1(SchemaGenerator):
    """Générateur du CONTRÔLE CI : introspecte une fois, reconstitue le miroir.

    À n'utiliser que via ``manage.py spectacular --generator-class`` depuis
    ``scripts/check_openapi_schema.py``. Le service HTTP du schéma
    (``/api/schema/``) garde le générateur par défaut.
    """

    def __init__(self, *args, **kwargs):
        # L'URLconf réduite est CE module (il expose `urlpatterns` ci-dessous),
        # sauf si l'appelant en impose une explicitement.
        if not kwargs.get('urlconf') and not kwargs.get('patterns'):
            kwargs['urlconf'] = _MODULE
        elargir_cache_source_location()
        super().__init__(*args, **kwargs)

    def parse(self, input_request, public):
        chemins = super().parse(input_request, public)
        etendre_miroir_v1(chemins, _prefixes_sans_jumeau_v1())
        return chemins


#: URLconf dérivée (racine moins le montage `api/v1/`). Voir l'en-tête.
urlpatterns = _monter_urlpatterns()
