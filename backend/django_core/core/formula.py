"""FG390 — Champs personnalisés calculés (formules), évaluateur sûr.

Couche de FONDATION : fournit un évaluateur d'EXPRESSIONS sûr et déterministe
que n'importe quelle app (en particulier ``customfields`` pour un type
``FORMULA``) peut appeler pour calculer la valeur d'un champ à partir des autres
champs — SANS que ``core`` n'importe une app métier (contrat import-linter
``core-foundation-is-a-base-layer``).

Sécurité
--------

L'évaluation N'UTILISE PAS ``eval`` sur du code arbitraire : l'expression est
parsée en AST (``ast.parse(mode='eval')``) et SEULS des nœuds explicitement
autorisés sont visités (littéraux, opérations arithmétiques/booléennes/de
comparaison, noms de variables fournis dans le contexte, et un petit jeu de
fonctions sûres). Tout le reste — appels de fonctions arbitraires, attributs,
indexation, lambdas, compréhensions, imports — lève ``FormulaError``. Aucune
boucle, aucun accès au système. Division par zéro / nom inconnu → ``FormulaError``
(jamais d'exception non maîtrisée).
"""
from __future__ import annotations

import ast
import operator

__all__ = ['FormulaError', 'evaluer_formule', 'valider_formule']


class FormulaError(Exception):
    """Formule invalide ou non évaluable (entrée non fiable maîtrisée)."""


# Opérateurs binaires/unaires autorisés.
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}
_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

# Fonctions sûres autorisées (pas d'effet de bord, pas d'accès système).
_SAFE_FUNCS = {
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
    'int': int,
    'float': float,
    'len': len,
}

# Garde-fou anti-DoS : exposant de puissance borné.
_MAX_POW = 1000


def _eval_node(node, context):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, context)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool, str)) or node.value is None:
            return node.value
        raise FormulaError('Littéral non autorisé.')
    if isinstance(node, ast.Name):
        if node.id in context:
            return context[node.id]
        raise FormulaError(f'Variable inconnue : {node.id!r}')
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise FormulaError('Opérateur binaire non autorisé.')
        left = _eval_node(node.left, context)
        right = _eval_node(node.right, context)
        if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) \
                and abs(right) > _MAX_POW:
            raise FormulaError('Exposant trop grand.')
        try:
            return op(left, right)
        except ZeroDivisionError:
            raise FormulaError('Division par zéro.')
        except TypeError as exc:
            raise FormulaError(str(exc))
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise FormulaError('Opérateur unaire non autorisé.')
        return op(_eval_node(node.operand, context))
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, context) for v in node.values]
        if isinstance(node.op, ast.And):
            result = True
            for v in values:
                result = result and v
            return result
        result = False
        for v in values:
            result = result or v
        return result
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        for op_node, comparator in zip(node.ops, node.comparators):
            op = _CMP_OPS.get(type(op_node))
            if op is None:
                raise FormulaError('Comparateur non autorisé.')
            right = _eval_node(comparator, context)
            if not op(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        cond = _eval_node(node.test, context)
        return (_eval_node(node.body, context) if cond
                else _eval_node(node.orelse, context))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_FUNCS:
            raise FormulaError('Appel de fonction non autorisé.')
        if node.keywords:
            raise FormulaError('Arguments nommés non autorisés.')
        args = [_eval_node(a, context) for a in node.args]
        try:
            return _SAFE_FUNCS[node.func.id](*args)
        except (TypeError, ValueError) as exc:
            raise FormulaError(str(exc))
    raise FormulaError(
        f'Élément non autorisé : {type(node).__name__}')


def evaluer_formule(expression, context=None):
    """Évalue une formule sûre sur ``context`` (dict variable→valeur).

    Renvoie la valeur calculée. Toute expression non sûre ou non évaluable lève
    ``FormulaError`` (jamais une exception non maîtrisée).
    """
    context = dict(context or {})
    if not isinstance(expression, str) or not expression.strip():
        raise FormulaError('Expression vide.')
    try:
        tree = ast.parse(expression, mode='eval')
    except SyntaxError as exc:
        raise FormulaError(f'Syntaxe invalide : {exc.msg}')
    return _eval_node(tree, context)


def valider_formule(expression, variables=None):
    """Valide qu'une formule est sûre + n'utilise que ``variables`` connues.

    Renvoie ``(ok: bool, erreur: str)``. Évalue à blanc avec un contexte de
    zéros pour repérer une variable inconnue / un nœud interdit, sans exécuter
    d'effet de bord (l'évaluateur n'en a aucun).
    """
    variables = list(variables or [])
    probe = {v: 0 for v in variables}
    try:
        evaluer_formule(expression, probe)
    except FormulaError as exc:
        # Une division par zéro à la sonde n'est PAS une erreur de validité.
        if 'Division par zéro' in str(exc):
            return True, ''
        return False, str(exc)
    return True, ''
