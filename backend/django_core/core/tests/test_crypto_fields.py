"""Tests YHARD1 — chiffrement au repos des champs sensibles (key-gated).

Couvre les trois garanties de la tâche, sans DB (helpers + méthodes de champ
directement, ``override_settings`` pour la clé) :

  * round-trip chiffré avec ``FIELD_ENCRYPTION_KEY`` posée (illisible en base,
    transparent au niveau ORM) ;
  * dégradation SANS clé = byte-identique à l'existant (aucun préfixe, aucune
    exception) ;
  * rétro-compatibilité : une valeur en clair (ligne historique) reste lisible
    même clé posée ; rotation de clés (MultiFernet) ; colonne TEXT.

Run :
    docker compose exec django_core python manage.py test \
        core.tests.test_crypto_fields -v 2
"""
from cryptography.fernet import Fernet
from django.test import SimpleTestCase, override_settings

from core import crypto_fields
from core.crypto_fields import (
    CIPHER_PREFIX,
    EncryptedCharField,
    EncryptedTextField,
    decrypt_value,
    encrypt_value,
)

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()


def _clear_cache():
    crypto_fields._build_fernet.cache_clear()


class EncryptWithKeyTests(SimpleTestCase):
    def setUp(self):
        _clear_cache()
        self.addCleanup(_clear_cache)

    @override_settings(FIELD_ENCRYPTION_KEY=KEY_A)
    def test_round_trip(self):
        plain = 'JBSWY3DPEHPK3PXP'  # secret TOTP base32
        token = encrypt_value(plain)
        self.assertNotEqual(token, plain)          # illisible en base
        self.assertTrue(token.startswith(CIPHER_PREFIX))
        self.assertNotIn(plain, token)             # pas de fuite en clair
        self.assertEqual(decrypt_value(token), plain)  # transparent ORM

    @override_settings(FIELD_ENCRYPTION_KEY=KEY_A)
    def test_encrypt_is_non_deterministic_but_decrypts(self):
        a = encrypt_value('secret')
        b = encrypt_value('secret')
        self.assertNotEqual(a, b)  # Fernet inclut un IV aléatoire
        self.assertEqual(decrypt_value(a), 'secret')
        self.assertEqual(decrypt_value(b), 'secret')

    @override_settings(FIELD_ENCRYPTION_KEY=KEY_A)
    def test_empty_and_none_pass_through(self):
        self.assertIsNone(encrypt_value(None))
        self.assertEqual(encrypt_value(''), '')
        self.assertIsNone(decrypt_value(None))

    @override_settings(FIELD_ENCRYPTION_KEY=KEY_A)
    def test_plaintext_legacy_row_stays_readable(self):
        # Valeur SANS marqueur (ligne écrite avant activation) → renvoyée telle
        # quelle, jamais une exception.
        self.assertEqual(decrypt_value('en clair'), 'en clair')

    @override_settings(FIELD_ENCRYPTION_KEY=KEY_A)
    def test_double_encrypt_is_idempotent(self):
        once = encrypt_value('x')
        twice = encrypt_value(once)
        self.assertEqual(once, twice)
        self.assertEqual(decrypt_value(twice), 'x')

    @override_settings(FIELD_ENCRYPTION_KEY=f'{KEY_B},{KEY_A}')
    def test_key_rotation_multifernet_decrypts_old(self):
        # Un jeton chiffré avec KEY_A doit rester déchiffrable quand KEY_B est
        # devenue la clé d'écriture primaire (MultiFernet déchiffre avec toutes).
        with override_settings(FIELD_ENCRYPTION_KEY=KEY_A):
            _clear_cache()
            token = encrypt_value('rotate-me')
        _clear_cache()
        self.assertEqual(decrypt_value(token), 'rotate-me')


class DegradeWithoutKeyTests(SimpleTestCase):
    def setUp(self):
        _clear_cache()
        self.addCleanup(_clear_cache)

    @override_settings(FIELD_ENCRYPTION_KEY='')
    def test_no_key_is_byte_identical(self):
        self.assertEqual(encrypt_value('secret'), 'secret')   # aucun préfixe
        self.assertEqual(decrypt_value('secret'), 'secret')

    @override_settings(FIELD_ENCRYPTION_KEY='')
    def test_no_key_leaves_marked_value_untouched(self):
        marked = f'{CIPHER_PREFIX}whatever'
        # Sans clé on ne peut pas déchiffrer : la valeur est renvoyée brute,
        # jamais une exception (réversibilité du retrait de clé).
        self.assertEqual(decrypt_value(marked), marked)


class EncryptedFieldTests(SimpleTestCase):
    def setUp(self):
        _clear_cache()
        self.addCleanup(_clear_cache)

    def test_stored_column_is_text(self):
        self.assertEqual(EncryptedCharField(max_length=64).get_internal_type(),
                         'TextField')
        self.assertEqual(EncryptedTextField().get_internal_type(), 'TextField')

    def test_charfield_keeps_max_length_kwarg(self):
        f = EncryptedCharField(max_length=128)
        name, path, args, kwargs = f.deconstruct()
        self.assertEqual(path, 'core.crypto_fields.EncryptedCharField')
        self.assertEqual(kwargs.get('max_length'), 128)

    @override_settings(FIELD_ENCRYPTION_KEY=KEY_A)
    def test_field_prep_and_from_db_round_trip(self):
        f = EncryptedCharField(max_length=64)
        stored = f.get_prep_value('cnss-12345')
        self.assertTrue(stored.startswith(CIPHER_PREFIX))
        back = f.from_db_value(stored, None, None)
        self.assertEqual(back, 'cnss-12345')

    @override_settings(FIELD_ENCRYPTION_KEY='')
    def test_field_no_key_prep_is_plain(self):
        f = EncryptedTextField()
        self.assertEqual(f.get_prep_value('rib-007'), 'rib-007')
        self.assertEqual(f.from_db_value('rib-007', None, None), 'rib-007')
