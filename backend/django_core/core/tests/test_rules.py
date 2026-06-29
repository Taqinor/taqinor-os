"""Tests FG367 — moteur de règles multi-critères (groupes ET/OU/NON) + actions
séquentielles. Couvre les fonctions PURES de :mod:`core.rules` :

  * :func:`evaluate_condition_group` — chaque opérateur de feuille, imbrication
    ET/OU/NON, court-circuit, tolérance aux champs absents et structures
    malformées (jamais d'exception) ;
  * :func:`validate_condition_group` — détecte op de groupe inconnu, conditions
    vides/non-liste, ``not`` mal cardinal, feuilles sans field/operator ;
  * :func:`sequential_actions` / :func:`iter_actions` — ordre préservé et arrêt
    sur erreur (stop-on-error) avec ou sans poursuite.
"""
from django.test import SimpleTestCase

from core.rules import (
    ActionOutcome,
    evaluate_condition_group,
    iter_actions,
    sequential_actions,
    validate_condition_group,
)


def leaf(field, operator, value=None):
    return {'field': field, 'operator': operator, 'value': value}


class LeafOperatorTests(SimpleTestCase):
    """Chaque opérateur de feuille pris isolément."""

    def test_eq_ne(self):
        ctx = {'stage': 'SIGNED'}
        self.assertTrue(evaluate_condition_group(leaf('stage', 'eq', 'SIGNED'), ctx))
        self.assertFalse(evaluate_condition_group(leaf('stage', 'eq', 'COLD'), ctx))
        self.assertTrue(evaluate_condition_group(leaf('stage', 'ne', 'COLD'), ctx))
        self.assertFalse(evaluate_condition_group(leaf('stage', 'ne', 'SIGNED'), ctx))

    def test_numeric_comparisons(self):
        ctx = {'montant': 5000}
        self.assertTrue(evaluate_condition_group(leaf('montant', 'gt', 1000), ctx))
        self.assertFalse(evaluate_condition_group(leaf('montant', 'gt', 9000), ctx))
        self.assertTrue(evaluate_condition_group(leaf('montant', 'gte', 5000), ctx))
        self.assertTrue(evaluate_condition_group(leaf('montant', 'lt', 9000), ctx))
        self.assertTrue(evaluate_condition_group(leaf('montant', 'lte', 5000), ctx))
        self.assertFalse(evaluate_condition_group(leaf('montant', 'lt', 5000), ctx))

    def test_in_not_in(self):
        ctx = {'canal': 'whatsapp'}
        self.assertTrue(
            evaluate_condition_group(
                leaf('canal', 'in', ['whatsapp', 'email']), ctx
            )
        )
        self.assertFalse(
            evaluate_condition_group(leaf('canal', 'in', ['email']), ctx)
        )
        self.assertTrue(
            evaluate_condition_group(leaf('canal', 'not_in', ['email']), ctx)
        )

    def test_contains_startswith(self):
        ctx = {'tags': ['vip', 'agricole'], 'nom': 'Coopérative Souss'}
        self.assertTrue(
            evaluate_condition_group(leaf('tags', 'contains', 'vip'), ctx)
        )
        self.assertFalse(
            evaluate_condition_group(leaf('tags', 'contains', 'froid'), ctx)
        )
        self.assertTrue(
            evaluate_condition_group(leaf('nom', 'startswith', 'Coop'), ctx)
        )

    def test_exists(self):
        ctx = {'email': 'x@y.ma', 'phone': None}
        # value truthy (défaut) ⇒ exige présent.
        self.assertTrue(evaluate_condition_group(leaf('email', 'exists'), ctx))
        # champ présent mais None reste « présent ».
        self.assertTrue(evaluate_condition_group(leaf('phone', 'exists'), ctx))
        self.assertFalse(evaluate_condition_group(leaf('gps', 'exists'), ctx))
        # exists value=False ⇒ exige ABSENT.
        self.assertTrue(
            evaluate_condition_group(leaf('gps', 'exists', False), ctx)
        )
        self.assertFalse(
            evaluate_condition_group(leaf('email', 'exists', False), ctx)
        )

    def test_unknown_operator_is_false(self):
        self.assertFalse(
            evaluate_condition_group(leaf('x', 'matches', '.*'), {'x': 'abc'})
        )


class MissingFieldToleranceTests(SimpleTestCase):
    """Un champ absent ⇒ feuille False, jamais d'exception (sauf 'exists')."""

    def test_missing_field_is_false_not_raise(self):
        ctx = {}
        for op in ('eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in',
                   'not_in', 'contains', 'startswith'):
            self.assertFalse(
                evaluate_condition_group(leaf('absent', op, 1), ctx),
                msg=f'{op} sur champ absent devrait être False',
            )

    def test_incompatible_types_are_false(self):
        # 'abc' > 3 lèverait TypeError → capturé → False.
        self.assertFalse(
            evaluate_condition_group(leaf('x', 'gt', 3), {'x': 'abc'})
        )
        # contains sur un int non-itérable → False, pas d'exception.
        self.assertFalse(
            evaluate_condition_group(leaf('x', 'contains', 'a'), {'x': 42})
        )

    def test_malformed_group_is_false(self):
        self.assertFalse(evaluate_condition_group(None, {}))
        self.assertFalse(evaluate_condition_group('not-a-dict', {}))
        self.assertFalse(evaluate_condition_group(42, {}))


class GroupLogicTests(SimpleTestCase):
    """Imbrication ET/OU/NON et court-circuit."""

    def test_and_group(self):
        ctx = {'stage': 'SIGNED', 'montant': 10000}
        group = {'op': 'and', 'conditions': [
            leaf('stage', 'eq', 'SIGNED'),
            leaf('montant', 'gte', 5000),
        ]}
        self.assertTrue(evaluate_condition_group(group, ctx))
        group['conditions'][1] = leaf('montant', 'gte', 50000)
        self.assertFalse(evaluate_condition_group(group, ctx))

    def test_or_group(self):
        ctx = {'canal': 'email'}
        group = {'op': 'or', 'conditions': [
            leaf('canal', 'eq', 'whatsapp'),
            leaf('canal', 'eq', 'email'),
        ]}
        self.assertTrue(evaluate_condition_group(group, ctx))
        group['conditions'] = [leaf('canal', 'eq', 'sms')]
        self.assertFalse(evaluate_condition_group(group, ctx))

    def test_not_group(self):
        ctx = {'stage': 'COLD'}
        group = {'op': 'not', 'conditions': [leaf('stage', 'eq', 'SIGNED')]}
        self.assertTrue(evaluate_condition_group(group, ctx))
        group = {'op': 'not', 'conditions': [leaf('stage', 'eq', 'COLD')]}
        self.assertFalse(evaluate_condition_group(group, ctx))

    def test_empty_and_is_true_empty_or_is_false(self):
        self.assertTrue(
            evaluate_condition_group({'op': 'and', 'conditions': []}, {})
        )
        self.assertFalse(
            evaluate_condition_group({'op': 'or', 'conditions': []}, {})
        )

    def test_default_op_is_and(self):
        # Groupe reconnu par la clé 'conditions' sans 'op' explicite ⇒ ET.
        group = {'conditions': [leaf('a', 'eq', 1), leaf('b', 'eq', 2)]}
        self.assertTrue(evaluate_condition_group(group, {'a': 1, 'b': 2}))
        self.assertFalse(evaluate_condition_group(group, {'a': 1, 'b': 9}))

    def test_deep_nesting(self):
        # (stage == SIGNED) AND ( (canal in [wa,email]) OR NOT(prio == basse) )
        ctx = {'stage': 'SIGNED', 'canal': 'sms', 'prio': 'haute'}
        group = {'op': 'and', 'conditions': [
            leaf('stage', 'eq', 'SIGNED'),
            {'op': 'or', 'conditions': [
                leaf('canal', 'in', ['whatsapp', 'email']),
                {'op': 'not', 'conditions': [leaf('prio', 'eq', 'basse')]},
            ]},
        ]}
        self.assertTrue(evaluate_condition_group(group, ctx))
        # casse la branche profonde : prio basse + canal sms ⇒ OR False ⇒ False.
        ctx['prio'] = 'basse'
        self.assertFalse(evaluate_condition_group(group, ctx))

    def test_short_circuit_does_not_raise_on_later_bad_leaf(self):
        # 'and' s'arrête au premier False : la feuille suivante (qui lèverait)
        # n'est même pas évaluée — mais de toute façon elle renvoie False.
        group = {'op': 'and', 'conditions': [
            leaf('x', 'eq', 'never'),     # False sur ctx vide → court-circuit
            leaf('y', 'gt', object()),    # ne doit pas planter le run
        ]}
        self.assertFalse(evaluate_condition_group(group, {}))


class ValidateConditionGroupTests(SimpleTestCase):
    def test_valid_tree_has_no_errors(self):
        group = {'op': 'and', 'conditions': [
            leaf('stage', 'eq', 'SIGNED'),
            {'op': 'not', 'conditions': [leaf('prio', 'eq', 'basse')]},
        ]}
        self.assertEqual(validate_condition_group(group), [])

    def test_unknown_group_op(self):
        errors = validate_condition_group(
            {'op': 'xor', 'conditions': [leaf('a', 'eq', 1)]}
        )
        self.assertTrue(any('xor' in e for e in errors))

    def test_not_requires_exactly_one(self):
        errors = validate_condition_group(
            {'op': 'not', 'conditions': [leaf('a', 'eq', 1), leaf('b', 'eq', 2)]}
        )
        self.assertTrue(any("'not'" in e for e in errors))

    def test_empty_conditions_flagged(self):
        errors = validate_condition_group({'op': 'and', 'conditions': []})
        self.assertTrue(errors)

    def test_conditions_not_a_list(self):
        errors = validate_condition_group({'op': 'and', 'conditions': 'nope'})
        self.assertTrue(any('conditions' in e for e in errors))

    def test_leaf_without_field_or_operator(self):
        errors = validate_condition_group({'operator': 'eq', 'value': 1})
        self.assertTrue(any('field' in e for e in errors))
        errors = validate_condition_group({'field': 'x', 'operator': 'bogus'})
        self.assertTrue(any('bogus' in e for e in errors))

    def test_non_dict_node(self):
        self.assertTrue(validate_condition_group('not-a-dict'))

    def test_nested_errors_carry_path(self):
        group = {'op': 'and', 'conditions': [
            {'field': 'x', 'operator': 'bogus'},
        ]}
        errors = validate_condition_group(group)
        self.assertTrue(any('conditions[0]' in e for e in errors))


class SequentialActionsTests(SimpleTestCase):
    def test_iter_actions_preserves_order_and_index(self):
        steps = list(iter_actions(['a', 'b', 'c']))
        self.assertEqual([s.index for s in steps], [0, 1, 2])
        self.assertEqual([s.descriptor for s in steps], ['a', 'b', 'c'])

    def test_iter_actions_empty(self):
        self.assertEqual(list(iter_actions(None)), [])
        self.assertEqual(list(iter_actions([])), [])

    def test_descriptor_only_run_marks_all_ok(self):
        run = sequential_actions(['x', 'y'])
        self.assertTrue(run.ok)
        self.assertEqual(run.completed, 2)
        self.assertIsNone(run.stopped_at)

    def test_runner_executes_in_order(self):
        seen = []
        run = sequential_actions(
            ['a', 'b', 'c'], runner=lambda step: seen.append(step.descriptor)
        )
        self.assertEqual(seen, ['a', 'b', 'c'])
        self.assertTrue(run.ok)

    def test_stop_on_error_via_exception(self):
        seen = []

        def runner(step):
            seen.append(step.descriptor)
            if step.descriptor == 'boom':
                raise RuntimeError('explosion')

        run = sequential_actions(['ok1', 'boom', 'never'], runner=runner)
        self.assertFalse(run.ok)
        self.assertEqual(run.stopped_at, 1)
        self.assertEqual(seen, ['ok1', 'boom'])  # 'never' jamais atteint
        self.assertEqual(run.completed, 2)
        self.assertIsInstance(run.outcomes[1].error, RuntimeError)

    def test_stop_on_error_via_outcome_ok_false(self):
        def runner(step):
            ok = step.descriptor != 'bad'
            return ActionOutcome(step=step, ok=ok)

        run = sequential_actions(['good', 'bad', 'after'], runner=runner)
        self.assertFalse(run.ok)
        self.assertEqual(run.stopped_at, 1)
        self.assertEqual(run.completed, 2)

    def test_continue_on_error_when_disabled(self):
        def runner(step):
            if step.descriptor == 'boom':
                raise ValueError('x')

        run = sequential_actions(
            ['a', 'boom', 'b'], runner=runner, stop_on_error=False
        )
        self.assertEqual(run.completed, 3)
        self.assertIsNone(run.stopped_at)
        # ok reflète qu'une étape a échoué même si on n'a pas stoppé.
        self.assertFalse(run.outcomes[1].ok)
