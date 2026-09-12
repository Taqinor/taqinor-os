# NTOBS9 — fenetres de maintenance planifiees. Migration ecrite a la main
# (INTERDIT manage.py sur cette lane) ; state Django equivalent a ce que
# `makemigrations` produirait pour `core.maintenance_windows.MaintenanceWindow`
# (nommage distinct de `core.maintenance` — NTPLT55, mode lecture-seule
# global, une fonctionnalite totalement differente).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('core', '0062_ntobs7_exportreversibiliterun'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceWindow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('region', models.CharField(blank=True, default='', max_length=60, verbose_name='Région')),
                ('debute_le', models.DateTimeField(verbose_name='Débute le')),
                ('termine_le', models.DateTimeField(verbose_name='Termine le')),
                ('impact', models.CharField(choices=[('aucun', 'Aucun'), ('degrade', 'Dégradé'), ('interruption', 'Interruption')], default='degrade', max_length=20, verbose_name='Impact')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('statut', models.CharField(choices=[('planifie', 'Planifié'), ('en_cours', 'En cours'), ('termine', 'Terminé'), ('annule', 'Annulé')], default='planifie', max_length=12, verbose_name='Statut')),
                ('notifie_24h_avant', models.BooleanField(default=False, verbose_name='Notifié 24h avant')),
                ('notifie_1h_avant', models.BooleanField(default=False, verbose_name='Notifié 1h avant')),
                ('company', models.ForeignKey(blank=True, help_text='NULL = annonce système large (toutes les sociétés).', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='maintenance_windows', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Fenêtre de maintenance',
                'verbose_name_plural': 'Fenêtres de maintenance',
                'ordering': ['debute_le'],
            },
        ),
    ]
