# NTHCM19 — délai de rappel des parcours obligatoires (réglage société).
#
# ADDITIF et SÛR : AddField avec un défaut (14) sur une table à UNE ligne par
# société — jamais un AddField(unique) ni un NOT NULL sans défaut (piège
# YDATA20).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0097_nthcm17_parcours_formation'),
    ]

    operations = [
        migrations.AddField(
            model_name='reglagerh',
            name='rappel_parcours_apres_jours',
            field=models.PositiveIntegerField(
                default=14,
                verbose_name='Rappel parcours obligatoire après (jours)'),
        ),
    ]
