"""YHARD1 — chiffrement au repos des données bancaires/sociales du profil paie.

``ProfilPaie.{numero_cnss, numero_amo, numero_cimr, rib}`` passent de
``CharField`` à ``EncryptedCharField`` (colonne TEXT). ADDITIF et RÉVERSIBLE :
sans ``FIELD_ENCRYPTION_KEY`` le comportement est octet-identique à l'existant,
les valeurs en clair déjà stockées restent lisibles, aucun RunPython de
transformation. ``salaire_base`` (Decimal) est HORS PÉRIMÈTRE (numérique).
"""
import core.crypto_fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0042_alter_bulletinpaie_type_bulletin'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profilpaie',
            name='numero_cnss',
            field=core.crypto_fields.EncryptedCharField(
                blank=True, default='', max_length=20, verbose_name='N° CNSS'),
        ),
        migrations.AlterField(
            model_name='profilpaie',
            name='numero_amo',
            field=core.crypto_fields.EncryptedCharField(
                blank=True, default='', max_length=20, verbose_name='N° AMO'),
        ),
        migrations.AlterField(
            model_name='profilpaie',
            name='numero_cimr',
            field=core.crypto_fields.EncryptedCharField(
                blank=True, default='', max_length=20, verbose_name='N° CIMR'),
        ),
        migrations.AlterField(
            model_name='profilpaie',
            name='rib',
            field=core.crypto_fields.EncryptedCharField(
                blank=True, default='', max_length=40, verbose_name='RIB'),
        ),
    ]
