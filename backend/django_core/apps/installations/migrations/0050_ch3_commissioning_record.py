# CH3 — Fiche de recette IEC 62446-1 structurée (CommissioningRecord) +
# relevés I-V par string (CommissioningIVReading).
#
# Additif : les champs libres historiques (Installation.mes_pv_notes /
# mes_production_test / mes_tension) sont CONSERVÉS lisibles — aucune donnée
# détruite. Migration écrite À LA MAIN, strictement cohérente avec les modèles.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('installations', '0049_ch1_stage_modele'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CommissioningRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('date_essai', models.DateField(blank=True, null=True)),
                ('technicien', models.CharField(
                    blank=True, max_length=120, null=True)),
                ('doc_dossier_ok', models.BooleanField(blank=True, null=True)),
                ('doc_schema_ok', models.BooleanField(blank=True, null=True)),
                ('doc_datasheets_ok',
                 models.BooleanField(blank=True, null=True)),
                ('visuel_structure_ok',
                 models.BooleanField(blank=True, null=True)),
                ('visuel_cablage_ok',
                 models.BooleanField(blank=True, null=True)),
                ('visuel_terre_ok', models.BooleanField(blank=True, null=True)),
                ('continuite_terre_ok',
                 models.BooleanField(blank=True, null=True)),
                ('continuite_terre_ohm', models.DecimalField(
                    blank=True, decimal_places=3, max_digits=8, null=True)),
                ('polarite_ok', models.BooleanField(blank=True, null=True)),
                ('isolement_mohm', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True)),
                ('isolement_ok', models.BooleanField(blank=True, null=True)),
                ('production_test_kw', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True)),
                ('production_attendue_kw', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True)),
                ('performance_ok', models.BooleanField(blank=True, null=True)),
                ('securite_coupure_ok',
                 models.BooleanField(blank=True, null=True)),
                ('securite_signalisation_ok',
                 models.BooleanField(blank=True, null=True)),
                ('resultat', models.CharField(
                    choices=[
                        ('en_cours', 'En cours'),
                        ('conforme', 'Conforme'),
                        ('reserves', 'Conforme avec réserves'),
                        ('non_conforme', 'Non conforme'),
                    ],
                    default='en_cours', max_length=14)),
                ('observations', models.TextField(blank=True, null=True)),
                ('ventes_recette_id',
                 models.PositiveIntegerField(blank=True, null=True)),
                ('date_creation',
                 models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commissioning_records',
                    to='authentication.company')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='commissioning_records_crees',
                    to=settings.AUTH_USER_MODEL)),
                ('installation', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commissioning_record',
                    to='installations.installation')),
            ],
            options={
                'verbose_name': 'Fiche de recette (IEC 62446-1)',
                'verbose_name_plural': 'Fiches de recette (IEC 62446-1)',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='CommissioningIVReading',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('string_label', models.CharField(max_length=60)),
                ('n_modules_serie',
                 models.PositiveSmallIntegerField(blank=True, null=True)),
                ('voc_mesure_v', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True)),
                ('isc_mesure_a', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True)),
                ('pmax_mesure_w', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True)),
                ('voc_attendu_v', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True)),
                ('isc_attendu_a', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=8, null=True)),
                ('pmax_attendu_w', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True)),
                ('ecart_pmax_pct', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=6, null=True)),
                ('defaut_detecte', models.BooleanField(default=False)),
                ('observations', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commissioning_iv_readings',
                    to='authentication.company')),
                ('record', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='iv_readings',
                    to='installations.commissioningrecord')),
            ],
            options={
                'verbose_name': 'Relevé I-V (recette chantier)',
                'verbose_name_plural': 'Relevés I-V (recette chantier)',
                'ordering': ['record', 'string_label'],
            },
        ),
    ]
