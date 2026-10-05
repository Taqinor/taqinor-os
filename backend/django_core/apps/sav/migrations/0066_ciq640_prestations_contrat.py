"""CIQ640 (Groupe CIQ, D-CIQ-12) — contrat O&M C&I : prestations nommées
(``PrestationContrat``), délai d'intervention en heures et origine (devis +
ligne O&M) sur ``ContratMaintenance``. Additive et réversible : colonnes et
table neuves, toutes NULL / False, aucune donnée existante modifiée."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('sav', '0065_agr615_releve_m3'),
    ]

    operations = [
        migrations.AddField(
            model_name='contratmaintenance',
            name='delai_intervention_heures',
            field=models.PositiveIntegerField(
                blank=True, help_text='Vide = non engagé.', null=True,
                verbose_name="Délai d'intervention (heures)"),
        ),
        migrations.AddField(
            model_name='contratmaintenance',
            name='origine_devis_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='contratmaintenance',
            name='origine_ligne_om_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='PrestationContrat',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('type', models.CharField(choices=[
                    ('nettoyage', 'Nettoyage'),
                    ('inspection', 'Inspection'),
                    ('thermographie', 'Thermographie'),
                    ('test_protections', 'Test des protections'),
                    ('supervision', 'Supervision'),
                    ('autre', 'Autre')], max_length=20)),
                ('libelle', models.CharField(max_length=160)),
                ('incluse', models.BooleanField(default=False)),
                ('frequence_an', models.PositiveSmallIntegerField(
                    blank=True, null=True)),
                ('prix_ht', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='prestations_contrat',
                    to='authentication.company')),
                ('contrat', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='prestations',
                    to='sav.contratmaintenance')),
            ],
            options={
                'verbose_name': 'Prestation de contrat',
                'verbose_name_plural': 'Prestations de contrat',
                'ordering': ['id'],
            },
        ),
    ]
