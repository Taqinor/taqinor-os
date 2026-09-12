# NTGRC14 — plans de traitement du risque + suivi. Table NEUVE.
# `cout_estime` est un DecimalField explicite (max_digits/decimal_places=2,
# MAD) — jamais un FloatField sur un montant (YDATA6/YDATA7).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0005_ntgrc13_risque_entreprise'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlanTraitementRisque',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('action', models.CharField(
                    max_length=255, verbose_name='Action')),
                ('responsable', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Responsable')),
                ('echeance', models.DateField(
                    blank=True, null=True, verbose_name='Échéance')),
                ('statut', models.CharField(
                    choices=[('a_faire', 'À faire'), ('en_cours', 'En cours'),
                             ('fait', 'Fait'), ('en_retard', 'En retard')],
                    default='a_faire', max_length=10,
                    verbose_name='Statut')),
                ('cout_estime', models.DecimalField(
                    decimal_places=2, default=0, max_digits=12,
                    verbose_name='Coût estimé (MAD)')),
                ('avancement_pct', models.PositiveSmallIntegerField(
                    default=0, verbose_name='Avancement (%)')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('risque', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='plans_traitement', to='grc.risqueentreprise',
                    verbose_name='Risque')),
            ],
            options={
                'verbose_name': 'Plan de traitement du risque',
                'verbose_name_plural': 'Plans de traitement du risque',
                'ordering': ['echeance', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='plantraitementrisque',
            index=models.Index(fields=['company', 'echeance'],
                               name='grc_plan_co_echeance_idx'),
        ),
        migrations.AddIndex(
            model_name='plantraitementrisque',
            index=models.Index(fields=['company', 'statut'],
                               name='grc_plan_co_statut_idx'),
        ),
    ]
