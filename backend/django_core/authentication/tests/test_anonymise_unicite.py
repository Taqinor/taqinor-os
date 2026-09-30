"""Unicité des faux du brouilleur anonymisé — défaut du 30/09/2026 sur les vraies
données de production.

Ce qui est verrouillé ici (SANS base : ``SimpleTestCase``, tourne sans
PostgreSQL) :
* deux valeurs réelles différentes ne partagent JAMAIS un faux dans un export
  (identifiants, e-mails, téléphones, noms, sociétés…) — l'ancien faux « ident »,
  qui gardait la longueur, donnait ~84 collisions sur 426 identifiants Odoo de
  3 chiffres, donc 80 leads sur 1 022 rejetés par ``uniq_lead_external_ref`` ;
* la même valeur réelle redonne TOUJOURS le même faux (mémo), quel que soit
  l'ordre de rencontre ;
* le format est gardé tant que l'espace n'est pas rempli à plus de moitié, puis
  on élargit d'un caractère ; un faux n'est jamais égal à sa valeur source ;
* un champ trop court pour l'unicité ne fait jamais planter l'export : le repli
  est COMPTÉ (jamais une valeur) ;
* une ligne que la base refuse à l'import est rapportée par NOM DE CONTRAINTE
  (``skip_reason``), jamais par sa valeur.

Les tests de base (aller-retour de ~400 leads Odoo, rapport des lignes
ignorées, réglages tarifaires) vivent dans ``test_anonymise.py``.
"""
from django.db import DataError, IntegrityError
from django.test import SimpleTestCase

from authentication import anonymise

SALT = b'\x07' * 32


def scrambler(salt=SALT):
    return anonymise.Scrambler(salt=salt)


class ScramblerInjectiveTest(SimpleTestCase):

    def test_odoo_sized_identifiers_get_distinct_same_format_fakes(self):
        scr = scrambler()
        reals = [str(100 + i) for i in range(426)]  # 3 chiffres, comme la prod
        fakes = [scr.fake('ident', r) for r in reals]
        self.assertEqual(len(set(fakes)), len(reals))
        self.assertTrue(all(len(f) == 3 and f.isdigit() for f in fakes))
        self.assertEqual(scr.widened, {})
        self.assertEqual(scr.exhausted, {})
        self.assertFalse(any(f == r for f, r in zip(fakes, reals)))

    def test_same_real_value_same_fake_whatever_the_order_or_length(self):
        reals = [str(100 + i) for i in range(426)]
        forward = scrambler()
        first = {r: forward.fake('ident', r) for r in reals}
        for r in reversed(reals):
            self.assertEqual(forward.fake('ident', r), first[r])
            # Une autre longueur max (autre champ) : même faux quand il tient.
            self.assertEqual(forward.fake('ident', r, max_length=100), first[r])
        # Même sel, autre ordre de rencontre : chaque valeur garde un faux
        # UNIQUE et stable (le faux exact peut différer : premier arrivé).
        backward = scrambler()
        second = {r: backward.fake('ident', r) for r in reversed(reals)}
        self.assertEqual(len(set(second.values())), len(reals))
        for r in reals:
            self.assertEqual(backward.fake('ident', r), second[r])

    def test_crowded_space_widens_by_one_character_and_stays_unique(self):
        scr = scrambler()
        reals = [str(i) for i in range(10)]  # tout l'espace « 1 chiffre »
        fakes = [scr.fake('ident', r) for r in reals]
        self.assertEqual(len(set(fakes)), 10)
        self.assertEqual([len(f) for f in fakes[:5]], [1] * 5)  # < moitié
        self.assertTrue(all(len(f) == 2 for f in fakes[5:]))  # passé la moitié
        self.assertTrue(all(f.isdigit() for f in fakes))
        self.assertEqual(scr.widened, {'ident': 5})
        self.assertFalse(any(f == r for f, r in zip(fakes, reals)))
        # Redemander ne change rien, même maintenant que l'espace est rempli.
        self.assertEqual([scr.fake('ident', r) for r in reals], fakes)
        # … ni avec une autre longueur max : le tirage retenu est rejoué.
        self.assertEqual([scr.fake('ident', r, max_length=50) for r in reals],
                         fakes)

    def test_every_injective_kind_stays_unique_at_scale(self):
        n = 3000
        samples = {
            'ident': [f'AB{i:06d}' for i in range(n)],
            'email': [f'user{i}@exemple.ma' for i in range(n)],
            'phone': [f'0661{i:06d}' for i in range(n)],
            'nom': [f'Client {i}' for i in range(n)],
            'societe': [f'Société {i}' for i in range(n)],
            'url': [f'https://exemple.ma/{i}' for i in range(n)],
            'texte': [f'remarque numéro {i}' for i in range(n)],
            'generic': [f'valeur{i}' for i in range(n)],
        }
        for kind, values in samples.items():
            with self.subTest(kind=kind):
                scr = scrambler()
                fakes = [scr.fake(kind, v) for v in values]
                self.assertEqual(len(set(fakes)), len(values))
                self.assertEqual(scr.exhausted, {})

    def test_identifier_is_case_and_space_sensitive_but_names_are_not(self):
        scr = scrambler()
        # L'index unique de la base est sensible à la casse : « ab12 » et
        # « AB12 » sont DEUX identifiants, donc deux faux.
        self.assertNotEqual(scr.fake('ident', 'ab12'), scr.fake('ident', 'AB12'))
        self.assertNotEqual(scr.fake('ident', ' 12'), scr.fake('ident', '12'))
        # Un nom / un e-mail : casse et espaces ignorés (regroupements gardés).
        self.assertEqual(scr.fake('nom', 'Bennani'), scr.fake('nom', ' bennani '))
        self.assertEqual(scr.fake('email', 'X@y.ma'),
                         scr.fake('email', ' x@Y.MA '))

    def test_phone_equivalence_and_non_numeric_values_stay_distinct(self):
        scr = scrambler()
        self.assertEqual(scr.fake('phone', '+212 6 61 11 22 33'),
                         scr.fake('phone', '0661112233'))
        self.assertNotEqual(scr.fake('phone', '0661112233'),
                            scr.fake('phone', '0661112234'))
        # Deux valeurs sans aucun chiffre ne se réduisent pas à « rien ».
        self.assertNotEqual(scr.fake('phone', 'N/A'), scr.fake('phone', 'inconnu'))

    def test_pool_kinds_stay_deterministic_finite_pools(self):
        scr = scrambler()
        prenoms = {scr.fake('prenom', f'Prénom{i}') for i in range(300)}
        self.assertLessEqual(len(prenoms), len(anonymise._PRENOMS))
        self.assertEqual(scr.fake('prenom', 'Amine'), scr.fake('prenom', ' amine'))
        self.assertEqual(scr.fake('adresse', '3 douar Ouled Qsiba'),
                         scr.fake('adresse', '3 douar Ouled Qsiba'))
        self.assertEqual(scr.exhausted, {})

    def test_max_length_is_respected_and_uniqueness_survives_truncation(self):
        scr = scrambler()
        reals = [f'{i:04d}' for i in range(6000)]  # champ de 4 caractères
        fakes = [scr.fake('ident', r, max_length=4) for r in reals]
        self.assertEqual(len(set(fakes)), len(reals))
        self.assertTrue(all(len(f) <= 4 for f in fakes))
        self.assertEqual(scr.exhausted, {})
        for kind in ('nom', 'email', 'phone', 'societe'):
            with self.subTest(kind=kind):
                self.assertLessEqual(len(scr.fake(kind, 'Zaki', max_length=5)), 5)

    def test_exhausted_space_falls_back_and_is_counted_never_raises(self):
        class Tiny(anonymise.Scrambler):
            def _build(self, kind, dig, value, width):
                return f'F{dig[0] % 3}'  # trois faux possibles seulement

        scr = Tiny(salt=SALT)
        fakes = [scr.fake('generic', f'valeur {i}') for i in range(5)]
        self.assertEqual(len(set(fakes[:3])), 3)  # les trois premiers : uniques
        self.assertEqual(scr.exhausted, {'generic': 2})  # les suivants : repli
        self.assertLessEqual(set(fakes), {'F0', 'F1', 'F2'})

    def test_blank_and_none_pass_through(self):
        scr = scrambler()
        self.assertIsNone(scr.fake('nom', None))
        self.assertEqual(scr.fake('nom', '   '), '   ')
        self.assertEqual(scr.fake('ident', ''), '')

    def test_a_fake_never_equals_its_source_even_in_a_one_slot_space(self):
        scr = scrambler()
        for real in [str(i) for i in range(10)] + ['A', 'AB', '---', '00']:
            with self.subTest(real=real):
                self.assertNotEqual(scr.fake('ident', real), real)

    def test_not_a_dictionary_attack_two_salts_never_agree(self):
        a, b = scrambler(b'\x01' * 32), scrambler(b'\x02' * 32)
        agree = sum(a.fake('ident', str(i)) == b.fake('ident', str(i))
                    for i in range(100, 600))
        # 500 identifiants sur 10³ faux : hasard seul, jamais une correspondance.
        self.assertLess(agree, 25)


class _Diag:
    """Ce que psycopg expose dans ``exc.diag`` (schéma, jamais une valeur)."""

    def __init__(self, constraint_name=None, column_name=None):
        self.constraint_name = constraint_name
        self.column_name = column_name


class _DriverError(Exception):
    """Le pilote (psycopg2/psycopg) : ``diag`` + un message qui CITE la valeur."""

    def __init__(self, message, diag):
        super().__init__(message)
        self.diag = diag


def _django_error(exc_class, cause):
    """Une exception Django enchaînée comme le fait ``DatabaseErrorWrapper``."""
    try:
        raise exc_class('détail privé') from cause
    except exc_class as exc:
        return exc


class SkipReasonTest(SimpleTestCase):
    """Le rapport d'import ne disait que ``IntegrityError=80`` : on ne savait pas
    POURQUOI 80 leads sautaient. Il nomme désormais la contrainte de base."""

    def test_constraint_name_is_reported_when_the_driver_gives_it(self):
        cause = _DriverError('Key (external_id)=(777) already exists.',
                             _Diag(constraint_name='uniq_lead_external_ref'))
        key = anonymise.skip_reason(_django_error(IntegrityError, cause))
        self.assertEqual(key, 'IntegrityError[uniq_lead_external_ref]')
        # Le message du pilote cite la valeur : il n'est JAMAIS lu.
        self.assertNotIn('777', key)
        self.assertNotIn('already exists', key)

    def test_rows_are_grouped_per_constraint_not_per_class(self):
        unique = _DriverError('x', _Diag(constraint_name='crx24_client_email_unique_ci'))
        other = _DriverError('x', _Diag(constraint_name='uniq_lead_external_ref'))
        keys = {anonymise.skip_reason(_django_error(IntegrityError, c))
                for c in (unique, other, unique)}
        self.assertEqual(keys, {'IntegrityError[crx24_client_email_unique_ci]',
                                'IntegrityError[uniq_lead_external_ref]'})

    def test_not_null_violation_names_its_column(self):
        cause = _DriverError('null value in column "phone"',
                             _Diag(column_name='phone'))
        self.assertEqual(
            anonymise.skip_reason(_django_error(IntegrityError, cause)),
            'IntegrityError[colonne phone]')

    def test_falls_back_to_the_class_name_without_driver_information(self):
        bare = _DriverError('too long', _Diag())
        self.assertEqual(anonymise.skip_reason(_django_error(DataError, bare)),
                         'DataError')
        self.assertEqual(anonymise.skip_reason(IntegrityError('x')),
                         'IntegrityError')  # aucune exception d'origine
        self.assertEqual(anonymise.skip_reason(ValueError('valeur privée')),
                         'ValueError')
        no_diag = _django_error(IntegrityError, RuntimeError('autre pilote'))
        self.assertEqual(anonymise.skip_reason(no_diag), 'IntegrityError')
