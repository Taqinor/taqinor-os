# Generated 2026-06-29 — FG179 Suivi péremption/contrôle des EPI à durée de vie

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0018_dotationepi"),
    ]

    operations = [
        migrations.AddField(
            model_name='epicatalogue',
            name='duree_vie_mois',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Durée de vie (mois)'),
        ),
        migrations.AddField(
            model_name='epicatalogue',
            name='intervalle_controle_mois',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Intervalle de contrôle (mois)'),
        ),
        migrations.AddField(
            model_name='dotationepi',
            name='date_peremption',
            field=models.DateField(
                blank=True, null=True,
                verbose_name='Date de péremption'),
        ),
        migrations.AddField(
            model_name='dotationepi',
            name='date_prochain_controle',
            field=models.DateField(
                blank=True, null=True,
                verbose_name='Date de prochain contrôle'),
        ),
        migrations.AddIndex(
            model_name='dotationepi',
            index=models.Index(
                fields=['company', 'date_peremption'],
                name='rh_dotepi_comp_perem_idx'),
        ),
        migrations.AddIndex(
            model_name='dotationepi',
            index=models.Index(
                fields=['company', 'date_prochain_controle'],
                name='rh_dotepi_comp_ctrl_idx'),
        ),
    ]
