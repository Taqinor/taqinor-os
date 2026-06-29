# Generated 2026-06-29 — FG170 Registre de présence chantier (émargement)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("rh", "0011_affectationroster"),
    ]

    operations = [
        migrations.CreateModel(
            name='PresenceChantier',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('installation_id', models.PositiveIntegerField(
                    verbose_name='Installation (ID)')),
                ('date', models.DateField(verbose_name='Date')),
                ('statut', models.CharField(
                    choices=[
                        ('present', 'Présent'),
                        ('absent', 'Absent'),
                        ('retard', 'En retard'),
                        ('parti_tot', 'Parti tôt'),
                    ],
                    default='present', max_length=10,
                    verbose_name='Statut')),
                ('heure_arrivee', models.TimeField(
                    blank=True, null=True, verbose_name="Heure d'arrivée")),
                ('heure_depart', models.TimeField(
                    blank=True, null=True, verbose_name='Heure de départ')),
                ('emarge', models.BooleanField(
                    default=False, verbose_name='Émargé')),
                ('emarge_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Émargé le')),
                ('note', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Note')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_presences_chantier',
                    to='authentication.company',
                    verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='presences_chantier',
                    to='rh.dossieremploye',
                    verbose_name='Employé')),
                ('emarge_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='rh_presences_emargees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Émargé par')),
            ],
            options={
                'verbose_name': 'Présence chantier',
                'verbose_name_plural': 'Présences chantier',
                'ordering': ['-date', 'installation_id', 'employe'],
            },
        ),
        migrations.AddIndex(
            model_name='presencechantier',
            index=models.Index(
                fields=['company', 'installation_id', 'date'],
                name='rh_presence_inst_date_idx'),
        ),
        migrations.AddIndex(
            model_name='presencechantier',
            index=models.Index(
                fields=['company', 'employe', 'date'],
                name='rh_presence_emp_date_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='presencechantier',
            unique_together={
                ('company', 'employe', 'installation_id', 'date')},
        ),
    ]
