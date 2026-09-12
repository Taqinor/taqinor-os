# NTOBS14 — historique d'uptime en frise chronologique 90 jours. Migration
# ecrite a la main (INTERDIT manage.py sur cette lane) ; state Django
# equivalent a ce que `makemigrations` produirait pour
# `apps.statuspage.models.UptimeDayBucket`.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('statuspage', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UptimeDayBucket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('composant', models.CharField(max_length=120, verbose_name='Composant')),
                ('region', models.CharField(blank=True, default='', max_length=60, verbose_name='Région')),
                ('date', models.DateField(verbose_name='Date')),
                ('statut_pire_du_jour', models.CharField(choices=[('operational', 'Opérationnel'), ('degraded', 'Dégradé'), ('partial_outage', 'Panne partielle'), ('major_outage', 'Panne majeure')], default='operational', max_length=20, verbose_name='Pire statut du jour')),
                ('echantillons_total', models.PositiveIntegerField(default=0, verbose_name='Échantillons observés')),
                ('echantillons_operationnels', models.PositiveIntegerField(default=0, verbose_name='Échantillons opérationnels')),
                ('pct_disponible_jour', models.DecimalField(decimal_places=2, default=100, max_digits=5, verbose_name='Disponibilité mesurée (%)')),
                ('company', models.ForeignKey(blank=True, help_text='NULL = composant système, partagé entre tous les tenants.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='statuspage_uptime_buckets', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Bucket de disponibilité (jour)',
                'verbose_name_plural': 'Buckets de disponibilité (jour)',
                'ordering': ['-date'],
            },
        ),
        migrations.AddConstraint(
            model_name='uptimedaybucket',
            constraint=models.UniqueConstraint(fields=('company', 'composant', 'region', 'date'), name='statuspage_uptimebucket_jour'),
        ),
        migrations.AddIndex(
            model_name='uptimedaybucket',
            index=models.Index(fields=['composant', '-date'], name='statuspage_uptime_cd_idx'),
        ),
    ]
