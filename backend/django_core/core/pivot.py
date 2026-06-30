"""FG380 — Constructeur de tableau croisé (pivot / crosstab), fondation.

Construit un tableau croisé interactif (lignes / colonnes / mesures) à partir de
données déjà scopées par société — transformation de données PURE, sans aucun
import d'app métier (contrat import-linter ``core-foundation-is-a-base-layer``)
et sans accès base. L'appelant (reporting, parametres…) passe une liste de DICTS
purs + une spécification ; ``core`` calcule l'agrégat croisé.

Spécification (``PivotSpec``)
-----------------------------

* ``rows``    : liste de clés servant d'axe LIGNES (groupement).
* ``columns`` : liste de clés servant d'axe COLONNES (croisement) — optionnel.
* ``measure`` : clé numérique à agréger (ignorée pour ``count``).
* ``agg``     : ``'sum'`` | ``'count'`` | ``'avg'`` | ``'min'`` | ``'max'``.

Le résultat est un dict sérialisable :

    {
        "row_keys":  [...],        # tuples de valeurs de lignes
        "col_keys":  [...],        # tuples de valeurs de colonnes
        "cells":     {row: {col: valeur}},
        "row_totals": {row: valeur},
        "col_totals": {col: valeur},
        "grand_total": valeur,
    }
"""
from __future__ import annotations

_AGGS = {'sum', 'count', 'avg', 'min', 'max'}


class PivotSpec:
    """Spécification d'un tableau croisé (validation à la construction)."""

    def __init__(self, *, rows, columns=None, measure=None, agg='sum'):
        self.rows = list(rows or [])
        self.columns = list(columns or [])
        self.measure = measure
        self.agg = agg
        if not self.rows and not self.columns:
            raise ValueError('Au moins un axe (rows ou columns) est requis.')
        if self.agg not in _AGGS:
            raise ValueError(f'Agrégation inconnue : {self.agg!r}')
        if self.agg != 'count' and not self.measure:
            raise ValueError("Une mesure est requise sauf pour l'agrégat "
                             "« count ».")


def _key(record, fields):
    """Tuple-clé d'un enregistrement pour des champs donnés (vide → ('∅',))."""
    if not fields:
        return ('',)
    return tuple(str(record.get(f, '')) for f in fields)


def _aggregate(values, agg):
    """Réduit une liste de valeurs selon l'agrégat (déterministe, tolérant)."""
    if agg == 'count':
        return len(values)
    nums = []
    for v in values:
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            continue
    if not nums:
        return 0
    if agg == 'sum':
        return sum(nums)
    if agg == 'avg':
        return sum(nums) / len(nums)
    if agg == 'min':
        return min(nums)
    if agg == 'max':
        return max(nums)
    return 0  # pragma: no cover — agg validé en amont.


def build_pivot(records, spec: PivotSpec) -> dict:
    """Calcule le tableau croisé de ``records`` selon ``spec`` (pur).

    ``records`` : itérable de dicts. Retourne un dict sérialisable (cf. module).
    Ne lève pas sur des données partielles : une clé absente vaut ''.
    """
    # Regroupe les valeurs de mesure par (row_key, col_key).
    buckets: dict = {}
    row_keys = []
    col_keys = []
    seen_rows = set()
    seen_cols = set()
    for rec in records:
        rk = _key(rec, spec.rows)
        ck = _key(rec, spec.columns)
        if rk not in seen_rows:
            seen_rows.add(rk)
            row_keys.append(rk)
        if ck not in seen_cols:
            seen_cols.add(ck)
            col_keys.append(ck)
        val = rec.get(spec.measure) if spec.measure else None
        buckets.setdefault((rk, ck), []).append(val)

    row_keys.sort()
    col_keys.sort()

    cells: dict = {}
    row_totals: dict = {}
    col_totals: dict = {ck: [] for ck in col_keys}
    all_values = []
    for rk in row_keys:
        cells[rk] = {}
        row_vals = []
        for ck in col_keys:
            vals = buckets.get((rk, ck), [])
            cells[rk][ck] = _aggregate(vals, spec.agg)
            row_vals.extend(vals)
            col_totals[ck].extend(vals)
            all_values.extend(vals)
        row_totals[rk] = _aggregate(row_vals, spec.agg)

    return {
        'row_keys': [list(rk) for rk in row_keys],
        'col_keys': [list(ck) for ck in col_keys],
        'cells': {','.join(rk): {','.join(ck): cells[rk][ck]
                                 for ck in col_keys}
                  for rk in row_keys},
        'row_totals': {','.join(rk): row_totals[rk] for rk in row_keys},
        'col_totals': {','.join(ck): _aggregate(col_totals[ck], spec.agg)
                       for ck in col_keys},
        'grand_total': _aggregate(all_values, spec.agg),
        'agg': spec.agg,
        'measure': spec.measure or '',
    }
