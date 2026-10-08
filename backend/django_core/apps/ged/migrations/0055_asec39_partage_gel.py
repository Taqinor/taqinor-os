"""ASEC39 — gel d'un partage GED après trop d'échecs de mot de passe
(compteur par partage, en base). Additif, revertable."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0054_adoc14_demandeapprobation_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='partageged',
            name='echecs_mdp',
            field=models.PositiveSmallIntegerField(
                default=0, verbose_name='échecs de mot de passe consécutifs'),
        ),
        migrations.AddField(
            model_name='partageged',
            name='gele_jusqua',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="gelé jusqu'à"),
        ),
    ]
