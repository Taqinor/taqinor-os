"""CADV107 — `reactivation_k3`, `reactivation_k6_p1` et `reactivation_k6_p2`
entrent dans `MessageTemplate.Cle` (réactivation des dormants, D-CADV-8/11).

`AlterField(choices)` UNIQUEMENT — même patron que 0089 : aucune donnée n'est
touchée, aucune ligne n'est créée. Les textes par défaut vivent dans
`MESSAGE_TEMPLATE_DEFAULTS` (du code) ; une société ne reçoit une ligne que le
jour où elle personnalise son message.
"""
from django.db import migrations, models

from apps.parametres.models_messages import MessageTemplate


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0131_redevance_compteur_aide'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagetemplate',
            name='cle',
            field=models.CharField(
                choices=MessageTemplate.Cle.choices, max_length=40),
        ),
    ]
