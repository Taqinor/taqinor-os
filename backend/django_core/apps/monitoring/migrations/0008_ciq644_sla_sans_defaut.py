# CIQ644 (Groupe CIQ, D-CIQ-12) — SLA de disponibilité SANS défaut : le taux
# garanti n'est plus pré-rempli à 98 %. AlterField réversible (nullable) ;
# les lignes existantes sont conservées telles quelles.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0007_ntnrg32_motif_limitation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sladisponibilite',
            name='disponibilite_garantie_pct',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True),
        ),
    ]
