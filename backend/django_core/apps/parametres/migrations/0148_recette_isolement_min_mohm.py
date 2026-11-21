"""ACAL669 — résistance d'isolement minimale à la recette (MΩ), réglage
société sans défaut. Additive : une colonne nullable, aucune donnée ;
réversible."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0147_textes_lignes_1711'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='recette_isolement_min_mohm',
            field=models.DecimalField(blank=True, decimal_places=2,
                                      max_digits=8, null=True),
        ),
    ]
