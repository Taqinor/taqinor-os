"""FG382 — BI embarqué : explorateur de données (query builder sans SQL).

Couche de FONDATION : fournit un query-builder GÉNÉRIQUE à sélection de champs,
filtres et agrégations, exécuté sur des « datasets » que les apps métier
ENREGISTRENT — ``core`` n'importe AUCUNE app métier (contrat import-linter
``core-foundation-is-a-base-layer``). Chaque dataset expose un nom, ses champs
sélectionnables et un fournisseur de queryset DÉJÀ scopé par société.

Conception
----------

* ``register_dataset(name, label, fields, queryset_provider)`` — une app métier
  enregistre un dataset. ``queryset_provider(company, user)`` doit renvoyer un
  queryset déjà filtré par société (la sécurité multi-tenant reste chez l'app
  propriétaire des données). ``fields`` est la liste blanche de chemins de
  champs interrogeables (jamais de champ hors liste → pas de fuite).
* ``run_query(name, company, user, spec)`` — exécute une spec de requête
  (sélection de champs, filtres, group_by + agrégations, tri, limite) en
  ``values()`` sur le queryset du dataset. Renvoie des lignes de dicts JSON —
  AUCUN SQL brut, AUCUN champ hors liste blanche.

Le modèle ``SavedQuery`` (multi-tenant) persiste une spec sauvegardée pour
rejouer une analyse ad-hoc.
"""
from __future__ import annotations

from django.db.models import Avg, Count, Max, Min, Sum

# Registre en mémoire : { dataset_name: {label, fields, provider} }.
_DATASETS: dict[str, dict] = {}

# Agrégations autorisées (liste blanche — jamais d'expression libre).
_AGGREGATES = {
    'count': Count,
    'sum': Sum,
    'avg': Avg,
    'min': Min,
    'max': Max,
}

# Suffixes de lookup de filtre autorisés (liste blanche).
_FILTER_LOOKUPS = {
    'exact', 'iexact', 'contains', 'icontains', 'gt', 'gte', 'lt', 'lte',
    'in', 'startswith', 'istartswith', 'isnull', 'date', 'year', 'month',
}


class DatasetInconnu(Exception):
    """Dataset non enregistré."""


class ChampNonAutorise(Exception):
    """Champ/filtre hors de la liste blanche du dataset."""


def register_dataset(name, label, fields, queryset_provider):
    """Enregistre un dataset interrogeable (idempotent).

    ``fields`` = liste blanche de chemins de champs. ``queryset_provider`` =
    callable ``(company, user) -> QuerySet`` déjà scopé société.
    """
    if not name or not callable(queryset_provider):
        raise ValueError('Dataset : nom + queryset_provider requis.')
    _DATASETS[name] = {
        'label': label or name,
        'fields': list(fields or []),
        'provider': queryset_provider,
    }


def list_datasets():
    """Catalogue normalisé des datasets enregistrés (rendu stable)."""
    out = [
        {'name': name, 'label': d['label'], 'fields': list(d['fields'])}
        for name, d in _DATASETS.items()
    ]
    out.sort(key=lambda d: d['name'])
    return out


def get_dataset(name):
    d = _DATASETS.get(name)
    if d is None:
        raise DatasetInconnu(f'Dataset inconnu : {name!r}')
    return d


def _field_root(path):
    """Racine d'un chemin de filtre (avant le premier suffixe de lookup)."""
    parts = path.split('__')
    # On retire un éventuel suffixe de lookup final connu.
    if len(parts) > 1 and parts[-1] in _FILTER_LOOKUPS:
        parts = parts[:-1]
    return '__'.join(parts)


def _check_fields(allowed, paths):
    allowed_set = set(allowed)
    for p in paths:
        if _field_root(p) not in allowed_set:
            raise ChampNonAutorise(f'Champ non autorisé : {p!r}')


def _apply_formula_measures(rows, formula_measures):
    """XPLT11 — ajoute des mesures FORMULE calculées sur les alias d'agrégats
    déjà présents dans chaque ligne (ex. ``ca / nb_devis``).

    ``formula_measures`` : liste de ``{alias, expression}``. Évaluée par
    ``core.formula.evaluer_formule`` — JAMAIS ``eval``. Une division par zéro
    donne une valeur VIDE (``None``) sur la ligne concernée (jamais une
    exception qui casserait tout le résultat) ; une expression ILLÉGALE (nœud
    interdit, variable inconnue autre que division par zéro) lève
    ``FormulaError`` — remontée telle quelle à l'appelant, qui la traduit en
    400."""
    from .formula import evaluer_formule, FormulaError

    if not formula_measures:
        return rows
    # Valide la légalité de CHAQUE formule une fois, sur la première ligne
    # (ou un contexte vide) — une expression illégale doit lever même si le
    # jeu de résultats est vide.
    probe_context = dict(rows[0]) if rows else {}
    for fm in formula_measures:
        try:
            evaluer_formule(fm['expression'], probe_context)
        except FormulaError as exc:
            if 'Division par zéro' not in str(exc):
                raise
    for row in rows:
        for fm in formula_measures:
            try:
                row[fm['alias']] = evaluer_formule(fm['expression'], row)
            except FormulaError as exc:
                if 'Division par zéro' in str(exc):
                    row[fm['alias']] = None
                else:
                    raise
    return rows


def run_query(name, company, user, spec):
    """Exécute une spec de requête sur un dataset (sans SQL brut).

    ``spec`` (dict) :
      * ``select`` : liste de champs à projeter (``values``) ;
      * ``filters`` : dict ``{chemin__lookup: valeur}`` (liste blanche) ;
      * ``group_by`` : liste de champs de regroupement ;
      * ``aggregates`` : liste de ``{alias, fn, field}`` (fn ∈ _AGGREGATES) ;
      * ``formula_measures`` : liste de ``{alias, expression}`` (XPLT11) —
        mesures CALCULÉES sur les alias d'``aggregates`` déjà produits,
        évaluées par ``core.formula`` (jamais ``eval``) ; division par zéro
        → valeur vide sur la ligne, expression illégale → ``FormulaError``
        (400 côté vue) ;
      * ``order_by`` : liste de champs de tri (préfixe ``-`` autorisé) ;
      * ``limit`` : entier (borné à 5000).

    Renvoie une liste de dicts. La sécurité société est portée par le
    ``queryset_provider`` du dataset (déjà scopé). Tout champ hors liste blanche
    lève ``ChampNonAutorise``.
    """
    dataset = get_dataset(name)
    allowed = dataset['fields']
    qs = dataset['provider'](company, user)

    spec = spec or {}
    select = list(spec.get('select') or [])
    filters = dict(spec.get('filters') or {})
    group_by = list(spec.get('group_by') or [])
    aggregates = list(spec.get('aggregates') or [])
    formula_measures = list(spec.get('formula_measures') or [])
    order_by = list(spec.get('order_by') or [])
    limit = spec.get('limit')

    _check_fields(allowed, list(filters.keys()))
    _check_fields(allowed, select)
    _check_fields(allowed, group_by)
    _check_fields(allowed, [o.lstrip('-') for o in order_by])
    _check_fields(allowed, [a.get('field') for a in aggregates if a.get('field')])

    if filters:
        qs = qs.filter(**filters)

    annotations = {}
    for agg in aggregates:
        fn = _AGGREGATES.get(agg.get('fn'))
        alias = agg.get('alias') or f"{agg.get('fn')}_{agg.get('field', '')}"
        if fn is None:
            raise ChampNonAutorise(f"Agrégation non autorisée : {agg.get('fn')!r}")
        field = agg.get('field') or 'id'
        annotations[alias] = fn(field)

    if group_by:
        qs = qs.values(*group_by)
        if annotations:
            qs = qs.annotate(**annotations)
    elif annotations:
        # Agrégation globale (sans group_by) → un seul dict.
        rows = [qs.aggregate(**annotations)]
        return _apply_formula_measures(rows, formula_measures)
    else:
        qs = qs.values(*(select or allowed))

    if order_by:
        qs = qs.order_by(*order_by)

    try:
        lim = int(limit) if limit is not None else 1000
    except (TypeError, ValueError):
        lim = 1000
    lim = max(1, min(lim, 5000))
    rows = list(qs[:lim])
    return _apply_formula_measures(rows, formula_measures)
