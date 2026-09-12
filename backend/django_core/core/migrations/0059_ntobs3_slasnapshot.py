# NTOBS3 — rapport SLA mensuel par tenant. Migration écrite à la main
# (INTERDIT manage.py sur cette lane) ; state Django équivalent à ce que
# `makemigrations` produirait pour `core.sla.SlaSnapshot`.
import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('core', '0058_ntext20_21_ui_extensions'),
    ]

    operations = [
        migrations.CreateModel(
            name='SlaSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('periode', models.DateField(help_text='Premier jour du mois couvert par ce snapshot.', verbose_name='Période (mois)')),
                ('uptime_pct', models.DecimalField(decimal_places=4, max_digits=7, verbose_name='Disponibilité (%)')),
                ('latence_p95_ms', models.PositiveIntegerField(blank=True, help_text='None = aucune mesure disponible pour cette période (jamais un chiffre inventé).', null=True, verbose_name='Latence P95 (ms)')),
                ('genere_le', models.DateTimeField(default=timezone.now, verbose_name='Généré le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='core_slasnapshot_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Rapport SLA mensuel',
                'verbose_name_plural': 'Rapports SLA mensuels',
                'ordering': ['-periode'],
            },
        ),
        migrations.AddConstraint(
            model_name='slasnapshot',
            constraint=models.UniqueConstraint(fields=('company', 'periode'), name='core_slasnapshot_co_periode'),
        ),
    ]
