"""NTDATA41 — `KpiAlerte.mode_detection` : seuil | variation | anomalie.

Colonne ADDITIVE avec un défaut INERTE (``seuil``) : toutes les alertes
existantes gardent exactement le comportement d'avant — comparer la valeur du
jour. Ajouter une colonne avec un défaut constant est une opération de
métadonnées en PostgreSQL 11+.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0021_ntdata37_abonnement_dashboard_query'),
    ]

    operations = [
        migrations.AddField(
            model_name='kpialerte',
            name='mode_detection',
            field=models.CharField(
                choices=[('seuil', 'Seuil sur la valeur'),
                         ('variation',
                          'Variation vs période précédente (%)'),
                         ('anomalie', "Écart à l'habitude (z-score)")],
                default='seuil', max_length=12,
                verbose_name='Mode de détection'),
        ),
    ]
