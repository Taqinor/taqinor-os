"""Équipe commerciale qui reçoit les nouveaux leads (rotation entre ses
membres). ADDITIF : un booléen faux par défaut, aucun comportement ne change
tant qu'aucune équipe n'est cochée. Réversible : ``migrate crm 0140``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0140_acrm70_messagetemplate_unique_langue'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipecommerciale',
            name='recoit_leads',
            field=models.BooleanField(
                default=False, verbose_name='Reçoit les nouveaux leads'),
        ),
    ]
