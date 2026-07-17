# NTEDU27 — Discipline et incidents.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('education', '0012_ligneecheance_cantine_montant'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='IncidentDiscipline',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date', models.DateField(verbose_name='Date')),
                ('type', models.CharField(choices=[('retard', 'Retard'), ('comportement', 'Comportement'), ('absence_injustifiee', 'Absence injustifiée'), ('autre', 'Autre')], max_length=25, verbose_name="Type d'incident")),
                ('gravite', models.CharField(choices=[('mineur', 'Mineur'), ('moyen', 'Moyen'), ('majeur', 'Majeur')], max_length=10, verbose_name='Gravité')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('statut', models.CharField(choices=[('ouvert', 'Ouvert'), ('en_traitement', 'En traitement'), ('clos', 'Clos')], default='ouvert', max_length=15, verbose_name='Statut')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('eleve', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='incidents_discipline', to='education.eleve', verbose_name='Élève')),
                ('signale_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='education_incidents_signales', to=settings.AUTH_USER_MODEL, verbose_name='Signalé par')),
            ],
            options={
                'verbose_name': 'Incident de discipline',
                'verbose_name_plural': 'Incidents de discipline',
                'ordering': ['-date'],
            },
        ),
    ]
