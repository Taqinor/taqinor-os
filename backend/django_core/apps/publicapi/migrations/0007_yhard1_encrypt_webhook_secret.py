"""YHARD1 — chiffrement au repos du secret de signature webhook.

``Webhook.secret`` (secret partagé HMAC-SHA256) passe de ``CharField`` à
``EncryptedCharField`` (colonne TEXT). ADDITIF et RÉVERSIBLE : sans
``FIELD_ENCRYPTION_KEY`` le comportement est octet-identique à l'existant, les
secrets en clair déjà stockés restent lisibles, aucun RunPython de
transformation.
"""
import core.crypto_fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('publicapi', '0006_yopsb11_webhookdeliveryarchive'),
    ]

    operations = [
        migrations.AlterField(
            model_name='webhook',
            name='secret',
            field=core.crypto_fields.EncryptedCharField(max_length=128),
        ),
    ]
