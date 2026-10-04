# AGR606 (Groupe AGR, 02/10/2026) — réglage société « écart de recette
# pompage toléré (%) », NULL et SANS défaut (décision C5-12). Migration
# additive et réversible.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0114_agr513_realisation_segment'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='recette_pompage_ecart_max_pct',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True),
        ),
    ]
