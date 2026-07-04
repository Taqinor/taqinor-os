import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0032_xmfg13_ncr_ordre_assemblage'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReleveThermographie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chantier_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID du chantier')),
                ('equipement_ref', models.CharField(max_length=255, verbose_name='Référence équipement')),
                ('attachment_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='ID de la pièce jointe (image IR)')),
                ('campagne', models.CharField(choices=[('recette', 'Recette (baseline)'), ('suivi', 'Suivi périodique')], default='suivi', max_length=10, verbose_name='Campagne')),
                ('delta_t', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name='ΔT mesuré (°C)')),
                ('seuil_a_surveiller', models.DecimalField(decimal_places=2, default=5, max_digits=6, verbose_name='Seuil « à surveiller » (°C)')),
                ('seuil_intervention', models.DecimalField(decimal_places=2, default=15, max_digits=6, verbose_name='Seuil « intervention requise » (°C)')),
                ('classe_severite', models.CharField(choices=[('observation', 'Observation'), ('a_surveiller', 'À surveiller'), ('intervention_requise', 'Intervention requise')], default='observation', max_length=25, verbose_name='Classe de sévérité')),
                ('date_releve', models.DateField(blank=True, null=True, verbose_name='Date du relevé')),
                ('note', models.TextField(blank=True, default='', verbose_name='Note')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_releves_thermo', to='authentication.company', verbose_name='Société')),
                ('ncr', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='releves_thermo', to='qhse.nonconformite', verbose_name='NCR levée')),
                ('releve_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_releves_thermo', to=settings.AUTH_USER_MODEL, verbose_name='Relevé par')),
            ],
            options={
                'verbose_name': 'Relevé de thermographie',
                'verbose_name_plural': 'Relevés de thermographie',
                'ordering': ['-date_releve', '-id'],
            },
        ),
        migrations.CreateModel(
            name='CheckinSecurite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intervention_id', models.PositiveIntegerField(blank=True, null=True, verbose_name="ID de l'intervention")),
                ('site_ref', models.CharField(blank=True, default='', max_length=255, verbose_name='Site')),
                ('heure_checkin', models.DateTimeField(blank=True, null=True, verbose_name='Heure de check-in')),
                ('heure_checkout_prevue', models.DateTimeField(blank=True, null=True, verbose_name='Heure de check-out prévue')),
                ('heure_checkout_reelle', models.DateTimeField(blank=True, null=True, verbose_name='Heure de check-out réelle')),
                ('delai_escalade_min', models.PositiveIntegerField(default=30, verbose_name='Délai avant escalade (min)')),
                ('escalade_declenchee', models.BooleanField(default=False, verbose_name='Escalade déclenchée')),
                ('escalade_le', models.DateTimeField(blank=True, null=True, verbose_name='Escaladé le')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_checkins', to='authentication.company', verbose_name='Société')),
                ('technicien', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='qhse_checkins', to=settings.AUTH_USER_MODEL, verbose_name='Technicien')),
            ],
            options={
                'verbose_name': 'Check-in sécurité',
                'verbose_name_plural': 'Check-ins sécurité',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='relevethermographie',
            index=models.Index(fields=['company', 'equipement_ref'], name='qhse_thermo_co_equip'),
        ),
        migrations.AddIndex(
            model_name='checkinsecurite',
            index=models.Index(fields=['company', 'heure_checkout_prevue'], name='qhse_checkin_co_prevue'),
        ),
    ]
