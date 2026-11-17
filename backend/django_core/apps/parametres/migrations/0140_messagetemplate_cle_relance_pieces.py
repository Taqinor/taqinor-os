"""16/11/2026 — `relance_pieces` entre dans `MessageTemplate.Cle` (étape du suivi
« Relancer le client pour ses pièces », lead professionnel sans facture reçue).

`AlterField(choices)` UNIQUEMENT — même patron que 0132 : aucune donnée n'est
touchée, aucune ligne n'est créée. Le texte par défaut vit dans
`MESSAGE_TEMPLATE_DEFAULTS` (du code).
"""
from django.db import migrations, models

from apps.parametres.models_messages import MessageTemplate


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0139_gabarits_v4_seed_0609'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagetemplate',
            name='cle',
            field=models.CharField(
                choices=MessageTemplate.Cle.choices, max_length=40),
        ),
    ]
