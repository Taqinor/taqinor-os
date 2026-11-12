"""AMSG37 — `relance_devis` entre dans `MessageTemplate.Cle` (« Relancer ce
devis » de la liste des devis, texte servi par `whatsapp-preview`).

`AlterField(choices)` UNIQUEMENT — même patron que 0089 / 0132 : aucune donnée
n'est touchée, aucune ligne n'est créée. Le texte par défaut vit dans
`MESSAGE_TEMPLATE_DEFAULTS` (du code).
"""
from django.db import migrations, models

from apps.parametres.models_messages import MessageTemplate


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0136_companyprofile_devise_tenant'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagetemplate',
            name='cle',
            field=models.CharField(
                choices=MessageTemplate.Cle.choices, max_length=40),
        ),
    ]
