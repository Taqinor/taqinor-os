# XFSM13 — Re-vérification périodique IEC 62446-2 avec comparaison baseline.
# Additif : ajoute la nouvelle valeur d'enum `Intervention.type_intervention`
# (choices only — aucune colonne changée) et une seule nouvelle table
# (ReverificationMesure). Aucune migration destructive.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0071_xfsm12_instrument_etalonnage'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='intervention',
            name='type_intervention',
            field=models.CharField(
                choices=[
                    ('pose', 'Pose'),
                    ('raccordement', 'Raccordement'),
                    ('mise_en_service', 'Mise en service'),
                    ('controle', 'Contrôle'),
                    ('depannage', 'Dépannage'),
                    ('reverification_62446', 'Re-vérification IEC 62446-2'),
                ],
                max_length=20),
        ),
        migrations.CreateModel(
            name='ReverificationMesure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intervention_id', models.PositiveIntegerField()),
                ('isolement_mohm', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('continuite_terre_ohm', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True)),
                ('voc_comparaison', models.JSONField(blank=True, default=list)),
                ('isolement_ecart_pct', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ('seuil_alerte_pct', models.DecimalField(decimal_places=2, default=20, max_digits=5)),
                ('depassement_detecte', models.BooleanField(default=False)),
                ('reserve_id', models.PositiveIntegerField(blank=True, null=True)),
                ('observations', models.TextField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reverifications', to='authentication.company')),
                ('record_baseline', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reverifications', to='installations.commissioningrecord')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reverifications_creees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Re-vérification IEC 62446-2',
                'verbose_name_plural': 'Re-vérifications IEC 62446-2',
                'ordering': ['-date_creation'],
            },
        ),
    ]
