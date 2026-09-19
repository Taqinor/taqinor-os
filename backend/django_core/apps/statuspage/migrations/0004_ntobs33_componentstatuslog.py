# NTOBS33 — historique brut des changements de statut d'un composant.
# Migration écrite à la main (INTERDIT manage.py sur cette lane) ; state
# Django équivalent à ce que `makemigrations` produirait pour
# `apps.statuspage.models.ComponentStatusLog`.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('statuspage', '0003_ntobs15_statussubscriber'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComponentStatusLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('composant', models.CharField(max_length=120, verbose_name='Composant')),
                ('region', models.CharField(blank=True, default='', max_length=60, verbose_name='Région')),
                ('ancien_statut', models.CharField(blank=True, choices=[('operational', 'Opérationnel'), ('degraded', 'Dégradé'), ('partial_outage', 'Panne partielle'), ('major_outage', 'Panne majeure')], default='', help_text="Vide pour le tout premier enregistrement d'un composant.", max_length=20, verbose_name='Ancien statut')),
                ('nouveau_statut', models.CharField(choices=[('operational', 'Opérationnel'), ('degraded', 'Dégradé'), ('partial_outage', 'Panne partielle'), ('major_outage', 'Panne majeure')], max_length=20, verbose_name='Nouveau statut')),
                ('company', models.ForeignKey(blank=True, help_text='NULL = composant système, partagé entre tous les tenants.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='statuspage_component_logs', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Historique brut de statut composant',
                'verbose_name_plural': 'Historiques bruts de statut composant',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='componentstatuslog',
            index=models.Index(fields=['composant', '-created_at'], name='statuspage_compstatuslog_idx'),
        ),
    ]
