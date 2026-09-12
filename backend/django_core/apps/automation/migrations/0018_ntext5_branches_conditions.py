"""NTEXT5 — branches conditionnelles (SI/SINON) dans une automatisation.

Purement ADDITIF et RÉVERSIBLE : ``condition`` (nullable) et ``branche``
(défaut ``toujours``) sur ``AutomationStep``. Une étape existante sans
condition reste inconditionnelle, et ``toujours`` ne participe à aucune
exclusion mutuelle — comportement actuel STRICTEMENT inchangé tant qu'un
admin ne pose pas de condition/branche.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0017_ntext31_simulation_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='automationstep',
            name='condition',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='automationstep',
            name='branche',
            field=models.CharField(
                choices=[('si', 'Si'), ('sinon', 'Sinon'),
                         ('toujours', 'Toujours')],
                default='toujours', max_length=10),
        ),
    ]
