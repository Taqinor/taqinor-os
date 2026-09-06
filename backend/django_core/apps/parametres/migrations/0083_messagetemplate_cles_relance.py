"""MRY12 — les 25 clés du moteur de relances entrent dans `MessageTemplate.Cle`.

`AlterField(choices)` UNIQUEMENT : aucune donnée n'est touchée, aucune ligne
n'est créée. Les textes par défaut vivent dans `MESSAGE_TEMPLATE_DEFAULTS`
(du code, pas des lignes) — une société ne reçoit une ligne que le jour où
elle personnalise un message.
"""
from django.db import migrations, models

from apps.parametres.models_messages import MessageTemplate


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0082_companyprofile_fenetres_appel'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagetemplate',
            name='cle',
            field=models.CharField(
                choices=MessageTemplate.Cle.choices, max_length=40),
        ),
    ]
