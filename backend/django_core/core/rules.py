"""FG367 — Conditions multi-critères (groupes ET/OU/NON) + actions séquentielles.

Moteur de RÈGLES générique, fondation pure. Comme les autres modules de
``core`` (``core.forecast``, ``core.anomaly``…), il reste une couche de BASE —
contrat import-linter ``core-foundation-is-a-base-layer`` : il n'importe AUCUNE
app métier et n'utilise que la bibliothèque standard. Aucun modèle, donc aucune
migration : ce sont des fonctions PURES, déterministes, sans base de données ni
réseau.

L'app appelante (``apps.automation`` pour ses ``AutomationRule``, mais aussi
n'importe quelle autre) construit un ``context`` plat (un simple ``dict``) à
partir de SES propres données, puis :

  * appelle :func:`validate_condition_group` AVANT de persister un arbre de
    conditions saisi par l'utilisateur (renvoie une liste d'erreurs, vide si
    valide) ;
  * appelle :func:`evaluate_condition_group` pour savoir si la règle se
    déclenche (renvoie ``True``/``False``, court-circuite, tolère les champs
    absents — un champ manquant ⇒ feuille ``False``, jamais d'exception) ;
  * itère :func:`sequential_actions` pour exécuter plusieurs actions DANS
    L'ORDRE avec arrêt-sur-erreur (le moteur décrit le déroulé ; la DISPATCH
    réelle de chaque action reste chez l'appelant).

Format de l'arbre de conditions
--------------------------------
Un **groupe** : ``{'op': 'and'|'or'|'not', 'conditions': [<noeud>, ...]}``.
Une **feuille** : ``{'field': str, 'operator': str, 'value': <any>}``.
Un nœud est un groupe s'il contient la clé ``'conditions'`` (ou ``op`` ∈ groupes),
sinon il est traité comme une feuille. ``and``/``or`` acceptent N conditions ;
``not`` inverse exactement UNE condition (validation l'exige).

Opérateurs de feuille pris en charge : ``eq, ne, gt, gte, lt, lte, in, not_in,
contains, startswith, exists``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator

# Opérateurs logiques de groupe.
GROUP_OPERATORS = ('and', 'or', 'not')

# Opérateurs de feuille pris en charge.
LEAF_OPERATORS = (
    'eq', 'ne', 'gt', 'gte', 'lt', 'lte',
    'in', 'not_in', 'contains', 'startswith', 'exists',
)

# Sentinelle pour distinguer « champ absent » de « champ présent valant None ».
_MISSING = object()


def _is_group(node: Any) -> bool:
    """Un nœud est un GROUPE s'il porte un ``op`` logique ou une clé ``conditions``.

    Tolérant : tout ``dict`` non-feuille reconnaissable comme groupe l'est ;
    les autres dicts sont des feuilles.
    """
    if not isinstance(node, dict):
        return False
    op = node.get('op')
    if isinstance(op, str) and op.lower() in GROUP_OPERATORS:
        return True
    # Pas d'op logique mais une liste de conditions ⇒ groupe (op par défaut 'and').
    if 'conditions' in node and 'operator' not in node:
        return True
    return False


def _compare(left: Any, operator: str, right: Any) -> bool:
    """Applique un opérateur de feuille. Renvoie ``False`` sur toute erreur.

    ``left`` est la valeur du contexte (ou la sentinelle ``_MISSING`` si le champ
    est absent). Aucune exception ne remonte : un type incompatible (p.ex.
    ``'abc' > 3``) renvoie ``False``.
    """
    op = (operator or '').lower()

    # 'exists' raisonne sur la PRÉSENCE du champ, pas sur sa valeur.
    if op == 'exists':
        present = left is not _MISSING
        # value truthy (défaut True) ⇒ exige présent ; falsy ⇒ exige absent.
        want_present = True if right is None else bool(right)
        return present if want_present else not present

    # Pour tous les autres opérateurs, un champ absent ⇒ False (tolérance).
    if left is _MISSING:
        return False

    try:
        if op == 'eq':
            return bool(left == right)
        if op == 'ne':
            return bool(left != right)
        if op == 'gt':
            return left > right
        if op == 'gte':
            return left >= right
        if op == 'lt':
            return left < right
        if op == 'lte':
            return left <= right
        if op == 'in':
            return left in right
        if op == 'not_in':
            return left not in right
        if op == 'contains':
            return right in left
        if op == 'startswith':
            return str(left).startswith(str(right))
    except (TypeError, ValueError):
        return False
    # Opérateur inconnu : prudence ⇒ False (la validation le signale en amont).
    return False


def _evaluate_leaf(leaf: dict, context: dict) -> bool:
    """Évalue une feuille ``{field, operator, value}`` contre ``context``."""
    field_name = leaf.get('field')
    operator = leaf.get('operator')
    value = leaf.get('value')
    left = context.get(field_name, _MISSING) if isinstance(context, dict) else _MISSING
    return _compare(left, operator, value)


def evaluate_condition_group(group: Any, context: dict) -> bool:
    """Évalue un arbre de conditions (groupes ET/OU/NON imbriqués) contre ``context``.

    ``group`` : un groupe ``{'op', 'conditions'}`` ou directement une feuille
    ``{'field', 'operator', 'value'}``. ``context`` : ``dict`` plat des valeurs
    courantes. Court-circuite (``and`` s'arrête au premier ``False``, ``or`` au
    premier ``True``). TOLÉRANT : structure malformée ou champ absent ⇒ ``False``,
    jamais d'exception.

    Renvoie ``bool``.
    """
    if not isinstance(group, dict):
        return False

    if not _is_group(group):
        # Traité comme une feuille.
        return _evaluate_leaf(group, context)

    op = str(group.get('op', 'and')).lower()
    conditions = group.get('conditions')
    if not isinstance(conditions, (list, tuple)):
        conditions = []

    if op == 'not':
        # 'not' inverse exactement une condition ; tolère plusieurs en NON(ET).
        if not conditions:
            return True  # NON(rien) ≡ NON(False) ≡ True.
        return not all(
            evaluate_condition_group(c, context) for c in conditions
        )

    if op == 'or':
        # Court-circuit au premier True ; un groupe OU vide est False.
        for cond in conditions:
            if evaluate_condition_group(cond, context):
                return True
        return False

    # 'and' (défaut) : court-circuit au premier False ; un ET vide est True.
    for cond in conditions:
        if not evaluate_condition_group(cond, context):
            return False
    return True


def validate_condition_group(group: Any, *, _path: str = 'root') -> list[str]:
    """Valide la STRUCTURE d'un arbre de conditions avant persistance.

    Renvoie une liste de messages d'erreur (vide ⇒ structure valide). Vérifie
    récursivement : groupes bien formés (``op`` logique connu, ``conditions``
    liste non vide, ``not`` ⇒ exactement une condition) et feuilles bien formées
    (``field`` non vide, ``operator`` connu). N'évalue rien et ne lève jamais.
    """
    errors: list[str] = []

    if not isinstance(group, dict):
        errors.append(f'{_path}: le nœud doit être un objet (dict).')
        return errors

    if _is_group(group):
        op = group.get('op', 'and')
        if not isinstance(op, str) or op.lower() not in GROUP_OPERATORS:
            errors.append(
                f"{_path}: opérateur de groupe inconnu "
                f"{op!r} (attendu {', '.join(GROUP_OPERATORS)})."
            )
            op_norm = ''
        else:
            op_norm = op.lower()

        conditions = group.get('conditions')
        if not isinstance(conditions, (list, tuple)):
            errors.append(f"{_path}: 'conditions' doit être une liste.")
            conditions = []
        elif not conditions:
            errors.append(f"{_path}: groupe '{op_norm or op}' sans condition.")

        if op_norm == 'not' and len(conditions) != 1:
            errors.append(
                f"{_path}: le groupe 'not' doit contenir exactement une "
                f"condition (reçu {len(conditions)})."
            )

        for idx, cond in enumerate(conditions):
            errors.extend(
                validate_condition_group(cond, _path=f'{_path}.conditions[{idx}]')
            )
        return errors

    # Feuille.
    field_name = group.get('field')
    if not isinstance(field_name, str) or not field_name:
        errors.append(f"{_path}: feuille sans 'field' (chaîne non vide) valide.")
    operator = group.get('operator')
    if not isinstance(operator, str) or operator.lower() not in LEAF_OPERATORS:
        errors.append(
            f"{_path}: opérateur de feuille inconnu {operator!r} "
            f"(attendu {', '.join(LEAF_OPERATORS)})."
        )
    return errors


@dataclass
class ActionStep:
    """Une action à exécuter, dans l'ordre, par l'appelant.

    ``descriptor`` est l'action brute fournie par l'appelant (souvent un ``dict``
    ``{type, params}``). ``index`` est sa position 0-based dans la séquence.
    """

    index: int
    descriptor: Any


@dataclass
class ActionOutcome:
    """Résultat d'une étape exécutée (rempli par l'appelant via le helper)."""

    step: ActionStep
    ok: bool = True
    result: Any = None
    error: Any = None


@dataclass
class SequentialRun:
    """Compte rendu d'un déroulé séquentiel d'actions avec arrêt-sur-erreur."""

    outcomes: list[ActionOutcome] = field(default_factory=list)
    stopped_at: int | None = None  # index où l'on s'est arrêté (None = tout passé)

    @property
    def ok(self) -> bool:
        """``True`` si toutes les étapes ont réussi (aucun arrêt)."""
        return self.stopped_at is None

    @property
    def completed(self) -> int:
        """Nombre d'étapes effectivement exécutées (réussites avant arrêt inclus)."""
        return len(self.outcomes)


def iter_actions(actions: Iterable) -> Iterator[ActionStep]:
    """Itère les actions DANS L'ORDRE en :class:`ActionStep` (index + descripteur).

    Pur, sans effet de bord : se contente d'envelopper chaque action. ``actions``
    falsy (``None``…) ⇒ itérateur vide.
    """
    for index, descriptor in enumerate(actions or []):
        yield ActionStep(index=index, descriptor=descriptor)


def sequential_actions(
    actions: Iterable,
    runner: Callable[[ActionStep], Any] | None = None,
    *,
    stop_on_error: bool = True,
) -> SequentialRun:
    """Décrit/exécute une séquence d'actions avec sémantique arrêt-sur-erreur.

    Sans ``runner`` (défaut) : renvoie un :class:`SequentialRun` dont chaque
    :class:`ActionOutcome` est un simple marqueur ``ok=True`` — l'appelant garde
    alors la DISPATCH réelle et n'utilise que l'ordre/les index (cf.
    :func:`iter_actions`).

    Avec ``runner`` : chaque étape est passée à ``runner(step)`` dans l'ordre. Si
    ``runner`` lève une exception (ou renvoie un :class:`ActionOutcome` ``ok=False``)
    et ``stop_on_error`` est vrai, le déroulé S'ARRÊTE : ``stopped_at`` vaut
    l'index fautif et les actions suivantes ne sont pas tentées. ``runner`` ne
    fait jamais planter cette fonction : toute exception est capturée et
    convertie en :class:`ActionOutcome` ``ok=False``.

    Renvoie un :class:`SequentialRun`. Ne lève jamais.
    """
    run = SequentialRun()
    for step in iter_actions(actions):
        if runner is None:
            run.outcomes.append(ActionOutcome(step=step, ok=True))
            continue
        try:
            result = runner(step)
        except Exception as exc:  # noqa: BLE001 — on isole l'action de l'appelant.
            run.outcomes.append(ActionOutcome(step=step, ok=False, error=exc))
            if stop_on_error:
                run.stopped_at = step.index
                break
            continue
        if isinstance(result, ActionOutcome):
            outcome = result
        else:
            outcome = ActionOutcome(step=step, ok=True, result=result)
        run.outcomes.append(outcome)
        if not outcome.ok and stop_on_error:
            run.stopped_at = step.index
            break
    return run
