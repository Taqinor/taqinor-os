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

AUD801 — CHAMPS SOUS PERMISSION (``gated_fields``)
--------------------------------------------------
Le moteur n'avait AUCUNE notion de champ sous permission : ``sav_tickets``
déléguait explicitement le masquage de ``cout`` (coût interne d'un ticket) à
« l'appelant », et AUCUN des huit consommateurs ne le faisait — ni
``SavedQueryViewSet.run_adhoc`` (``IsAuthenticated`` seul, corps libre), ni le
drill, ni les formules, ni les widgets de tableau de bord, ni le cache BI, ni
le classeur, ni les rapports, ni l'extrait planifié vers SFTP/S3 (qui appelle
``run_query`` avec ``user=None`` littéral). N'importe quel rôle interne
récupérait les coûts bruts en JSON.

Le masquage est donc désormais DANS LE MOTEUR, une seule fois pour les huit
chemins : ``register_dataset(..., gated_fields={'cout': 'can_view_buy_prices'})``
associe un champ à un attribut de permission de l'utilisateur, et ``run_query``
écarte ce champ de TOUTES les positions de la spec — ``select``, ``filters``
(sinon on infère la valeur par dichotomie : ``{"cout__gt": X}`` + ``count``),
``group_by``, ``order_by``, ``aggregates`` (sinon ``{"fn":"sum",
"field":"cout"}`` rend le total des coûts) et la projection par DÉFAUT (une
spec SANS ``select`` projetait TOUS les champs). Permission absente OU
``user=None`` (tâche planifiée) ⇒ champ écarté, toujours. Un champ gated n'est
jamais une ERREUR (400) : il est silencieusement retiré, pour qu'un extrait
planifié continue de livrer ses colonnes légitimes.
"""
from __future__ import annotations

from django.db.models import Avg, Count, Max, Min, Sum

from core.analytics_db import analytics_queryset

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


def register_dataset(name, label, fields, queryset_provider,
                     cache_partage=False, gated_fields=None):
    """Enregistre un dataset interrogeable (idempotent).

    ``fields`` = liste blanche de chemins de champs. ``queryset_provider`` =
    callable ``(company, user) -> QuerySet`` déjà scopé société.

    NTDATA36 — ``cache_partage`` : par défaut FAUX, c.-à-d. qu'une entrée de
    pré-agrégation (``core.bi_cache``) est propre à un utilisateur, parce qu'un
    dataset peut masquer des champs selon ses droits. Un dataset dont le
    résultat ne dépend QUE de la société peut le déclarer VRAI pour partager
    l'entrée entre ses utilisateurs.

    AUD801 — ``gated_fields`` : dict ``{champ: attribut_de_permission}`` (ex.
    ``{'cout': 'can_view_buy_prices'}``). Le champ n'est rendu qu'aux
    utilisateurs pour lesquels ``getattr(user, attribut)`` est vrai ; il est
    écarté de toutes les positions de la spec sinon (et TOUJOURS quand
    ``user`` est ``None``). Un dataset qui déclare des champs gated ne peut PAS
    partager son cache : le résultat dépend du LECTEUR, pas seulement de la
    société — ``cache_partage`` est donc refusé avec ``gated_fields``.
    """
    if not name or not callable(queryset_provider):
        raise ValueError('Dataset : nom + queryset_provider requis.')
    gated = dict(gated_fields or {})
    if gated and cache_partage:
        raise ValueError(
            'Dataset %r : « cache_partage » est incompatible avec des champs '
            'sous permission (le résultat dépend du lecteur).' % name)
    _DATASETS[name] = {
        'label': label or name,
        'fields': list(fields or []),
        'provider': queryset_provider,
        'cache_partage': bool(cache_partage),
        'gated_fields': gated,
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


def champs_interdits(dataset, user):
    """AUD801 — champs ``gated_fields`` que ``user`` n'a PAS le droit de voir.

    ``user`` à ``None`` (extrait planifié, tâche) ⇒ TOUS les champs gated sont
    interdits : un chemin sans acteur ne peut pas prouver une permission.
    L'attribut de permission est lu par ``getattr`` (propriété du modèle
    utilisateur, ex. ``can_view_buy_prices``) — ``core`` reste fondation et
    n'importe aucun modèle d'app.
    """
    gated = (dataset or {}).get('gated_fields') or {}
    if not gated:
        return set()
    return {
        champ for champ, permission in gated.items()
        if user is None or not getattr(user, permission, False)
    }


def _sans_champs_interdits(interdits, select, filters, group_by, order_by,
                           aggregates):
    """Retire ``interdits`` de TOUTES les positions de la spec.

    Les cinq positions comptent : ``select`` (fuite directe), ``filters``
    (inférence par dichotomie ``{"cout__gt": X}`` + comptage), ``group_by``
    (les valeurs deviennent des clés de ligne), ``order_by`` (un tri révèle
    l'ordre relatif) et ``aggregates`` (une somme rend le total).
    """
    select = [f for f in select if _field_root(f) not in interdits]
    filters = {k: v for k, v in filters.items()
               if _field_root(k) not in interdits}
    group_by = [f for f in group_by if _field_root(f) not in interdits]
    order_by = [o for o in order_by
                if _field_root(o.lstrip('-')) not in interdits]
    aggregates = [a for a in aggregates
                  if _field_root(a.get('field') or '') not in interdits]
    return select, filters, group_by, order_by, aggregates


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
    # YHARD9 — lecture BI lourde : route vers le réplica analytique si configuré
    # (no-op strict sinon). Le queryset provider est DÉJÀ scopé société ; changer
    # la base de lecture ne touche pas le filtre `company`. Chemin 100 % lecture.
    qs = analytics_queryset(dataset['provider'](company, user))

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

    # AUD801 — masquage des champs sous permission, APRÈS la liste blanche (un
    # champ inconnu reste une erreur 400 ; un champ gated est silencieusement
    # écarté). ``allowed`` est réduit AUSSI : c'est lui qui sert de projection
    # par défaut quand la spec ne fournit pas de ``select``.
    interdits = champs_interdits(dataset, user)
    if interdits:
        allowed = [f for f in allowed if f not in interdits]
        select, filters, group_by, order_by, aggregates = (
            _sans_champs_interdits(interdits, select, filters, group_by,
                                   order_by, aggregates))

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
        # AUD801 — JAMAIS ``values()`` sans argument : cela projetterait TOUTES
        # les colonnes du modèle, champs gated compris. Une projection vidée
        # par le masquage retombe sur la liste blanche RÉDUITE, jamais sur le
        # modèle entier ; si elle est vide elle aussi, on ne rend que ``id``.
        projection = select or allowed or ['id']
        qs = qs.values(*projection)

    if order_by:
        qs = qs.order_by(*order_by)

    try:
        lim = int(limit) if limit is not None else 1000
    except (TypeError, ValueError):
        lim = 1000
    lim = max(1, min(lim, 5000))
    rows = list(qs[:lim])
    return _apply_formula_measures(rows, formula_measures)
