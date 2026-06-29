# Generated 2026-06-29 — FG171 Retards & absences injustifiées (marquage + compteur)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("rh", "0012_presencechantier"),
    ]

    operations = [
        migrations.CreateModel(
            name='IncidentPresence',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('type_incident', models.CharField(
                    choices=[
                        ('retard', 'Retard'),
                        ('absence_injustifiee', 'Absence injustifiée'),
                        ('depart_anticipe', 'Départ anticipé'),
                    ],
                    default='retard', max_length=20,
                    verbose_name="Type d'incident")),
                ('date', models.DateField(verbose_name='Date')),
                ('minutes_retard', models.PositiveIntegerField(
                    default=0, verbose_name='Minutes de retard')),
                ('justifie', models.BooleanField(
                    default=False, verbose_name='Justifié')),
                ('motif', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Motif')),
                ('justifie_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Justifié le')),
                ('note', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Note')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_incidents_presence',
                    to='authentication.company',
                    verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='incidents_presence',
                    to='rh.dossieremploye',
                    verbose_name='Employé')),
                ('justifie_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='rh_incidents_justifies',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Justifié par')),
            ],
            options={
                'verbose_name': 'Incident de présence',
                'verbose_name_plural': 'Incidents de présence',
                'ordering': ['-date', '-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='incidentpresence',
            index=models.Index(
                fields=['company', 'employe', 'date'],
                name='rh_incident_emp_date_idx'),
        ),
        migrations.AddIndex(
            model_name='incidentpresence',
            index=models.Index(
                fields=['company', 'type_incident'],
                name='rh_incident_comp_type_idx'),
        ),
    ]
