"""YHARD1 — chiffrement au repos des identifiants sensibles du dossier employé.

``DossierEmploye.{cin, cnss, cimr, amo, rib}`` passent de ``CharField`` à
``EncryptedCharField`` (colonne TEXT). ADDITIF et RÉVERSIBLE : sans
``FIELD_ENCRYPTION_KEY`` le comportement est octet-identique à l'existant, les
valeurs en clair déjà stockées restent lisibles, aucun RunPython de
transformation. ``groupe_sanguin`` / rémunérations numériques hors périmètre.
"""
import core.crypto_fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0082_dossieremploye_tiers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dossieremploye',
            name='cin',
            field=core.crypto_fields.EncryptedCharField(
                blank=True, default='', max_length=20, verbose_name='CIN'),
        ),
        migrations.AlterField(
            model_name='dossieremploye',
            name='cnss',
            field=core.crypto_fields.EncryptedCharField(
                blank=True, default='', max_length=20, verbose_name='N° CNSS'),
        ),
        migrations.AlterField(
            model_name='dossieremploye',
            name='cimr',
            field=core.crypto_fields.EncryptedCharField(
                blank=True, default='', max_length=20, verbose_name='N° CIMR'),
        ),
        migrations.AlterField(
            model_name='dossieremploye',
            name='amo',
            field=core.crypto_fields.EncryptedCharField(
                blank=True, default='', max_length=20, verbose_name='N° AMO'),
        ),
        migrations.AlterField(
            model_name='dossieremploye',
            name='rib',
            field=core.crypto_fields.EncryptedCharField(
                blank=True, default='', max_length=40, verbose_name='RIB'),
        ),
    ]
