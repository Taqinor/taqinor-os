# NTNRG14 — SLA de disponibilité (additive, hand-written comme 0002).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('installations', '0033_fg318_contrat_prix'),
        ('monitoring', '0004_odx16_abonnement_monitoring'),
    ]

    operations = [
        migrations.CreateModel(
            name='SlaDisponibilite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('disponibilite_garantie_pct', models.DecimalField(decimal_places=2, default=98, max_digits=5)),
                ('compensation_mad_par_jour_indispo', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('note', models.TextField(blank=True, default='')),
                # SCA4 — socle core.models.TenantModel (created_at/updated_at
                # au lieu de date_creation/date_modification à la main).
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sla_disponibilites', to='authentication.company')),
                ('installation', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='sla_disponibilite', to='installations.installation')),
            ],
            options={
                'verbose_name': 'SLA de disponibilité',
                'verbose_name_plural': 'SLA de disponibilité',
                'ordering': ['-updated_at'],
                'indexes': [models.Index(fields=['company', 'installation'], name='monitoring_sla_dispo_idx')],
            },
        ),
    ]
