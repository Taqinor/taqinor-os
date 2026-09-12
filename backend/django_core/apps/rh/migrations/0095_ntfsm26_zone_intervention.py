# NTFSM26 — zone géographique d'intervention sur le dossier employé.
#
# ADDITIF : champ libre, défaut '' — aucun dossier existant n'est modifié et
# aucun référentiel de villes n'est inventé pour ce seul besoin.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0094_nthcm15_plan_action_engagement'),
    ]

    operations = [
        migrations.AddField(
            model_name='dossieremploye',
            name='zone_intervention',
            field=models.CharField(
                blank=True, default='', max_length=120,
                verbose_name="Zone d'intervention"),
        ),
    ]
