"""YHARD1 — chiffrement au repos de la clé privée VAPID.

``VapidKeyPair.private_key`` (PEM) passe de ``TextField`` à
``EncryptedTextField`` (reste une colonne TEXT — pas de changement de type
colonne). ADDITIF et RÉVERSIBLE : sans ``FIELD_ENCRYPTION_KEY`` le comportement
est octet-identique à l'existant, la clé en clair déjà stockée reste lisible,
aucun RunPython de transformation.
"""
import core.crypto_fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0039_ntsec_security_event_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vapidkeypair',
            name='private_key',
            field=core.crypto_fields.EncryptedTextField(default=''),
        ),
    ]
