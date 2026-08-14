# NTRET11 — Carte de fidélité dématérialisée (QR) : CompteFidelite.code_qr.
from django.db import migrations, models

import apps.fidelite.models


class Migration(migrations.Migration):

    dependencies = [
        ('fidelite', '0002_ntret10_paliers'),
    ]

    operations = [
        migrations.AddField(
            model_name='comptefidelite',
            name='code_qr',
            field=models.CharField(
                default=apps.fidelite.models.generer_code_qr, editable=False,
                max_length=64, unique=True,
                help_text=(
                    'Jeton opaque non séquentiel (carte dématérialisée '
                    'NTRET11) — globalement unique : résout LUI-MÊME LA '
                    'société, jamais réutilisable pour un autre tenant.')),
        ),
    ]
