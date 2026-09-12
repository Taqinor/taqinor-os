# NTGRC15 — revues périodiques du risque (cadence + journal). Table NEUVE.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0006_ntgrc14_plan_traitement_risque'),
    ]

    operations = [
        migrations.CreateModel(
            name='RevueRisque',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date_revue', models.DateField(
                    verbose_name='Date de la revue')),
                ('revu_par', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Revu par')),
                ('decision', models.CharField(
                    choices=[('maintenu', "Maintenu en l'état"),
                             ('reclasse', 'Reclassé (cotation revue)'),
                             ('clos', 'Clos')],
                    default='maintenu', max_length=10,
                    verbose_name='Décision')),
                ('commentaire', models.TextField(
                    blank=True, default='', verbose_name='Commentaire')),
                ('prochaine_revue', models.DateField(
                    blank=True, null=True, verbose_name='Prochaine revue')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='grc_revuerisque_set',
                    to='authentication.company', verbose_name='Société')),
                ('risque', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='revues', to='grc.risqueentreprise',
                    verbose_name='Risque')),
            ],
            options={
                'verbose_name': 'Revue de risque',
                'verbose_name_plural': 'Revues de risque',
                'ordering': ['-date_revue', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='revuerisque',
            index=models.Index(fields=['company', 'date_revue'],
                               name='grc_revue_co_date_idx'),
        ),
    ]
