# NTAI29 — Snapshots de dérive (drift) des features d'un scorer.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
    ]

    operations = [
        migrations.CreateModel(
            name='DriftSnapshot',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name='ID'),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'modele',
                    models.CharField(
                        help_text='Nom du scorer surveillé (churn, win_proba, '
                                  'retard_paiement…).',
                        max_length=60),
                ),
                (
                    'date',
                    models.DateField(
                        help_text='Premier jour de la période observée.'),
                ),
                (
                    'distribution_json',
                    models.JSONField(
                        blank=True, default=dict,
                        help_text="{bucket: proportion} des features "
                                  "d'entrée observées."),
                ),
                (
                    'psi',
                    models.FloatField(
                        default=0.0,
                        help_text='Population Stability Index vs la baseline '
                                  '(0 = identique).'),
                ),
                (
                    'est_baseline',
                    models.BooleanField(
                        default=False,
                        help_text='Snapshot de référence auquel les suivants '
                                  'se comparent.'),
                ),
                (
                    'alerte_emise',
                    models.BooleanField(
                        default=False,
                        help_text='Une alerte de dérive a été notifiée pour '
                                  'ce snapshot.'),
                ),
                (
                    'company',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(app_label)s_%(class)s_set',
                        to='authentication.company', verbose_name='Société'),
                ),
            ],
            options={
                'verbose_name': 'Snapshot de dérive',
                'verbose_name_plural': 'Snapshots de dérive',
                'ordering': ['-date', 'modele'],
            },
        ),
        migrations.AddIndex(
            model_name='driftsnapshot',
            index=models.Index(
                fields=['company', 'modele', '-date'],
                name='ai_gov_drift_co_mod_date_idx'),
        ),
        migrations.AddConstraint(
            model_name='driftsnapshot',
            constraint=models.UniqueConstraint(
                fields=('company', 'modele', 'date'),
                name='uniq_driftsnapshot_company_modele_date'),
        ),
    ]
