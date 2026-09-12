"""NTDATA11 — `MetricDefinition.filtres` : la POPULATION d'une métrique.

Additive et revertable : défaut `{}` = aucun filtre = comportement d'avant.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('semantic', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='metricdefinition',
            name='filtres',
            field=models.JSONField(
                blank=True, default=dict,
                help_text='Filtres TOUJOURS appliqués (ex. {"actif": true}) — '
                          'la population que cette métrique mesure.',
                verbose_name='Filtres de la définition'),
        ),
    ]
