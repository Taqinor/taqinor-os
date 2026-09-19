# NTOBS21 — réglages de fiabilité par société (une ligne par société, OneToOne).
# Table NEUVE, purement additive : l'absence de ligne vaut les défauts déclarés
# au modèle, donc aucune société ne change de comportement à la migration et
# aucune donnée n'est à écrire.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0070_nti18n36_moduletoggle_rtl_pret'),
        ('authentication', '0013_customuser_poste_ref'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReliabilitySettings',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('notifier_maintenance_email', models.BooleanField(
                    default=True,
                    verbose_name='Prévenir par e-mail des maintenances')),
                ('notifier_quota_email', models.BooleanField(
                    default=True,
                    verbose_name='Prévenir par e-mail des quotas')),
                ('notifier_incident_region', models.CharField(
                    blank=True, default='', max_length=100, null=True,
                    help_text='Vide = tous les incidents, sans filtre de '
                              'région.',
                    verbose_name='Région suivie pour les incidents')),
                ('afficher_badge_sla_dashboard', models.BooleanField(
                    default=True,
                    verbose_name='Afficher le badge SLA sur le tableau de '
                                 'bord')),
                ('company', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reliability_settings',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Réglages de fiabilité',
                'verbose_name_plural': 'Réglages de fiabilité',
                'ordering': ['company_id'],
            },
        ),
    ]
