# Generated for XRH24 — rétention des candidatures rejetées (loi 09-08).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0059_remove_dossieremploye_rh_dossier_code_pointage_uniq_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='reglagerh',
            name='retention_candidatures_mois',
            field=models.PositiveIntegerField(
                default=24, verbose_name='Rétention candidatures (mois)'),
        ),
    ]
