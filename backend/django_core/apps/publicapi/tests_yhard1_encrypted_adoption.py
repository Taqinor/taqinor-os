"""Tests YHARD1 — ADOPTION du chiffrement au repos sur des modèles RÉELS (DB).

Le module ``test_crypto_fields`` couvre le champ/les helpers hors DB. Ici on
prouve, à travers l'ORM et la VRAIE colonne Postgres, que l'adoption sur des
modèles concrets respecte les trois garanties de la tâche :

  * avec ``FIELD_ENCRYPTION_KEY`` posée, la valeur est ILLISIBLE en base
    (jeton ``enc:``) mais TRANSPARENTE au passage ORM ;
  * SANS clé, la colonne est octet-identique à l'existant (aucun préfixe) ;
  * une ligne HISTORIQUE en clair reste lisible même clé posée ;
  * le scoping multi-tenant (filtre par ``company``) est INCHANGÉ — le
    chiffrement d'un champ non-indexé ne touche pas le filtrage.

On exerce ``publicapi.Webhook.secret`` (a une ``company`` FK → scoping) et
``authentication.CustomUser.totp_secret``.

Run :
    docker compose exec django_core python manage.py test \
        core.tests.test_yhard1_encrypted_adoption -v 2
"""
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings

from apps.publicapi.models import Webhook
from authentication.models import Company
from core import crypto_fields
from core.crypto_fields import CIPHER_PREFIX

KEY = Fernet.generate_key().decode()
User = get_user_model()


def _clear_cache():
    crypto_fields._build_fernet.cache_clear()


def _raw_column(model, pk, field_name):
    """Lit la valeur BRUTE (non déchiffrée) directement en base."""
    col = model._meta.get_field(field_name).column
    table = model._meta.db_table
    with connection.cursor() as cur:
        cur.execute(
            f'SELECT "{col}" FROM "{table}" WHERE id = %s', [pk])
        return cur.fetchone()[0]


class WebhookSecretEncryptedTests(TestCase):
    def setUp(self):
        _clear_cache()
        self.addCleanup(_clear_cache)
        self.co = Company.objects.create(slug='yh1-a', nom='YH1 A')

    @override_settings(FIELD_ENCRYPTION_KEY=KEY)
    def test_secret_unreadable_in_db_transparent_via_orm(self):
        hook = Webhook.objects.create(
            company=self.co, target_url='https://example.test/h',
            secret='top-secret-hmac', events=[])
        raw = _raw_column(Webhook, hook.pk, 'secret')
        self.assertTrue(raw.startswith(CIPHER_PREFIX))   # illisible en base
        self.assertNotIn('top-secret-hmac', raw)         # pas de fuite en clair
        # Transparent au niveau ORM (relecture depuis la base) :
        self.assertEqual(
            Webhook.objects.get(pk=hook.pk).secret, 'top-secret-hmac')

    @override_settings(FIELD_ENCRYPTION_KEY='')
    def test_no_key_is_byte_identical_in_db(self):
        hook = Webhook.objects.create(
            company=self.co, target_url='https://example.test/h',
            secret='plainval', events=[])
        raw = _raw_column(Webhook, hook.pk, 'secret')
        self.assertEqual(raw, 'plainval')                # aucun chiffrement
        self.assertEqual(Webhook.objects.get(pk=hook.pk).secret, 'plainval')

    @override_settings(FIELD_ENCRYPTION_KEY=KEY)
    def test_legacy_plaintext_row_reads_back(self):
        hook = Webhook.objects.create(
            company=self.co, target_url='https://example.test/h',
            secret='will-overwrite', events=[])
        # Simule une ligne écrite AVANT l'activation du chiffrement : on force
        # une valeur en clair directement en base (sans préfixe ``enc:``).
        table = Webhook._meta.db_table
        col = Webhook._meta.get_field('secret').column
        with connection.cursor() as cur:
            cur.execute(
                f'UPDATE "{table}" SET "{col}" = %s WHERE id = %s',
                ['legacy-clear', hook.pk])
        # Relue via l'ORM, la valeur claire historique est renvoyée telle quelle.
        self.assertEqual(
            Webhook.objects.get(pk=hook.pk).secret, 'legacy-clear')

    @override_settings(FIELD_ENCRYPTION_KEY=KEY)
    def test_tenant_scoping_unchanged(self):
        co_b = Company.objects.create(slug='yh1-b', nom='YH1 B')
        Webhook.objects.create(
            company=self.co, target_url='https://a.test/h',
            secret='sa', events=[])
        Webhook.objects.create(
            company=co_b, target_url='https://b.test/h',
            secret='sb', events=[])
        # Le filtre par société n'est pas affecté par le chiffrement du secret.
        own = Webhook.objects.filter(company=self.co)
        self.assertEqual(own.count(), 1)
        self.assertEqual(own.first().secret, 'sa')
        self.assertEqual(Webhook.objects.filter(company=co_b).count(), 1)


class TotpSecretEncryptedTests(TestCase):
    def setUp(self):
        _clear_cache()
        self.addCleanup(_clear_cache)
        self.co = Company.objects.create(slug='yh1-u', nom='YH1 U')

    @override_settings(FIELD_ENCRYPTION_KEY=KEY)
    def test_totp_secret_encrypted_in_db_transparent_via_orm(self):
        user = User.objects.create_user(
            username='yh1-user', password='x', company=self.co,
            role_legacy='admin')
        user.totp_secret = 'JBSWY3DPEHPK3PXP'
        user.save(update_fields=['totp_secret'])
        raw = _raw_column(User, user.pk, 'totp_secret')
        self.assertTrue(raw.startswith(CIPHER_PREFIX))
        self.assertNotIn('JBSWY3DPEHPK3PXP', raw)
        self.assertEqual(
            User.objects.get(pk=user.pk).totp_secret, 'JBSWY3DPEHPK3PXP')

    @override_settings(FIELD_ENCRYPTION_KEY='')
    def test_totp_secret_no_key_byte_identical(self):
        user = User.objects.create_user(
            username='yh1-user2', password='x', company=self.co,
            role_legacy='admin')
        user.totp_secret = 'PLAINTOTP'
        user.save(update_fields=['totp_secret'])
        raw = _raw_column(User, user.pk, 'totp_secret')
        self.assertEqual(raw, 'PLAINTOTP')
