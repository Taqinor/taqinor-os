"""17/11/2026 — `passation` et `appel_apres_reponse` entrent dans
`MessageTemplate.Cle` : leur texte par défaut existait (ACVI51) mais
Paramètres → Messages ne les listait pas, la société ne pouvait donc ni les
voir ni les adapter.

`AlterField(choices)` UNIQUEMENT — même patron que 0140/0141 : aucune donnée
n'est touchée, aucune ligne n'est créée. Les textes par défaut vivent dans
`MESSAGE_TEMPLATE_DEFAULTS` (du code).
"""
from django.db import migrations, models

from apps.parametres.models_messages import MessageTemplate


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0143_apres_devis_heures_cibles'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagetemplate',
            name='cle',
            field=models.CharField(
                choices=MessageTemplate.Cle.choices, max_length=40),
        ),
    ]
