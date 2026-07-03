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
* ``formula`` : XPLT11 — expression FORMULE ad-hoc (ex. ``'ca / nb_devis'``)
  évaluée sur les alias d'``extra_measures`` PAR CELLULE (via
  ``core.formula``, jamais ``eval``) ; division par zéro → cellule vide.
* ``extra_measures`` : liste de ``{alias, field, agg}`` supplémentaires
  calculées PAR CELLULE pour nourrir ``formula`` (ex. panier moyen =
  ``ca / nb_devis`` a besoin de deux agrégats bruts par cellule).

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

    def __init__(self, *, rows, columns=None, measure=None, agg='sum',
                 formula=None, extra_measures=None):
        self.rows = list(rows or [])
        self.columns = list(columns or [])
        self.measure = measure
        self.agg = agg
        # XPLT11 — mesure calculée ad-hoc (ex. « ca/nb_devis ») + les mesures
        # brutes supplémentaires qui l'alimentent (chacune {alias, field, agg}).
        self.formula = (formula or '').strip() or None
        self.extra_measures = list(extra_measures or [])
        if not self.rows and not self.columns:
            raise ValueError('Au moins un axe (rows ou columns) est requis.')
        if self.agg not in _AGGS:
            raise ValueError(f'Agrégation inconnue : {self.agg!r}')
        if self.agg != 'count' and not self.measure and not self.formula:
            raise ValueError("Une mesure est requise sauf pour l'agrégat "
                             "« count » ou une mesure formule.")
        for em in self.extra_measures:
            if em.get('agg') not in _AGGS:
                raise ValueError(
                    f"Agrégation inconnue pour la mesure « {em.get('alias')} » : "
                    f"{em.get('agg')!r}")


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


def _formula_cell_value(vals_by_alias, formula):
    """XPLT11 — évalue ``formula`` sur les agrégats bruts d'UNE cellule.

    ``vals_by_alias`` : ``{alias: valeur_agrégée}``. Division par zéro →
    ``None`` (cellule vide, jamais d'exception). Expression illégale → laisse
    remonter ``FormulaError`` (validée en amont par l'appelant)."""
    from .formula import evaluer_formule, FormulaError
    try:
        return evaluer_formule(formula, vals_by_alias)
    except FormulaError as exc:
        if 'Division par zéro' in str(exc):
            return None
        raise


def _build_pivot_formula(records, spec: PivotSpec) -> dict:
    """XPLT11 — variante ``build_pivot`` pour une mesure FORMULE ad-hoc.

    Calcule, PAR CELLULE, chacune des ``spec.extra_measures`` (mêmes règles
    d'agrégation que le pivot standard) puis évalue ``spec.formula`` sur ces
    alias. Totaux de ligne/colonne/global recalculent la formule sur les
    agrégats bruts de leur propre périmètre (jamais une moyenne de moyennes)."""
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
        buckets.setdefault((rk, ck), []).append(rec)

    row_keys.sort()
    col_keys.sort()

    def _cell_aggs(recs):
        return {
            em['alias']: _aggregate(
                [r.get(em['field']) for r in recs], em['agg'])
            for em in spec.extra_measures
        }

    # Valide la légalité de la formule une fois (contexte à zéros), avant de
    # parcourir toutes les cellules — une expression illégale doit lever même
    # sur un jeu de données vide.
    from .formula import valider_formule
    ok, err = valider_formule(
        spec.formula, [em['alias'] for em in spec.extra_measures])
    if not ok:
        from .formula import FormulaError
        raise FormulaError(err)

    cells: dict = {}
    row_totals: dict = {}
    col_recs: dict = {ck: [] for ck in col_keys}
    all_recs = []
    for rk in row_keys:
        cells[rk] = {}
        row_recs = []
        for ck in col_keys:
            recs = buckets.get((rk, ck), [])
            cells[rk][ck] = _formula_cell_value(_cell_aggs(recs), spec.formula)
            row_recs.extend(recs)
            col_recs[ck].extend(recs)
            all_recs.extend(recs)
        row_totals[rk] = _formula_cell_value(_cell_aggs(row_recs), spec.formula)

    return {
        'row_keys': [list(rk) for rk in row_keys],
        'col_keys': [list(ck) for ck in col_keys],
        'cells': {','.join(rk): {','.join(ck): cells[rk][ck]
                                 for ck in col_keys}
                  for rk in row_keys},
        'row_totals': {','.join(rk): row_totals[rk] for rk in row_keys},
        'col_totals': {','.join(ck): _formula_cell_value(
            _cell_aggs(col_recs[ck]), spec.formula) for ck in col_keys},
        'grand_total': _formula_cell_value(_cell_aggs(all_recs), spec.formula),
        'agg': 'formula',
        'measure': spec.formula,
    }


def build_pivot(records, spec: PivotSpec) -> dict:
    """Calcule le tableau croisé de ``records`` selon ``spec`` (pur).

    ``records`` : itérable de dicts. Retourne un dict sérialisable (cf. module).
    Ne lève pas sur des données partielles : une clé absente vaut ''.

    XPLT11 — si ``spec.formula`` est posée, délègue à ``_build_pivot_formula``
    (mesure calculée ad-hoc) ; sinon comportement INCHANGÉ (mesure simple)."""
    if spec.formula:
        return _build_pivot_formula(records, spec)

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
