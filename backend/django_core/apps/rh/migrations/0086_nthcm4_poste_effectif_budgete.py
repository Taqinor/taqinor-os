# NTHCM4 — effectif budgété par poste (headcount planning).
#
# ADDITIF : défaut 0 = AUCUNE limite posée, donc tous les postes existants
# restent NEUTRES (jamais « en dépassement ») après la migration.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0085_nthcm1_dossieremploye_manager'),
    ]

    operations = [
        migrations.AddField(
            model_name='poste',
            name='effectif_budgete',
            field=models.PositiveIntegerField(
                default=0, verbose_name='Effectif budgété'),
        ),
    ]
