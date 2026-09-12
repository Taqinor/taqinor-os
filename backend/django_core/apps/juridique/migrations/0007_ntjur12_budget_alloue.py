"""NTJUR12 — enveloppe budgétaire allouée au dossier.

Champ ADDITIF et nullable : NULL = aucune enveloppe fixée, le pourcentage
consommé reste alors indéfini (jamais une division par zéro, jamais un 0 %
trompeur).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('juridique', '0006_ntjur4_5_11_echeancier_honoraires'),
    ]

    operations = [
        migrations.AddField(
            model_name='dossierjuridique',
            name='budget_alloue',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=14, null=True,
                verbose_name='Budget alloué'),
        ),
    ]
