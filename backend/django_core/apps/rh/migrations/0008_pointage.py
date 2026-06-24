# Generated 2026-06-24 — FG166 Pointage clock-in/out

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("rh", "0007_dossieremploye_date_sortie_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name='Pointage',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('type_pointage', models.CharField(
                    choices=[
                        ('arrivee', 'Arrivée'),
                        ('depart', 'Départ'),
                        ('complet', 'Complet (arrivée + départ)'),
                    ],
                    default='arrivee', max_length=10,
                    verbose_name='Type')),
                ('heure_arrivee', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name="Heure d'arrivée")),
                ('heure_depart', models.DateTimeField(
                    blank=True, null=True,
                    verbose_name='Heure de départ')),
                ('arrivee_gps_lat', models.DecimalField(
                    blank=True, decimal_places=6, max_digits=9, null=True,
                    verbose_name='GPS arrivée — latitude')),
                ('arrivee_gps_lng', models.DecimalField(
                    blank=True, decimal_places=6, max_digits=9, null=True,
                    verbose_name='GPS arrivée — longitude')),
                ('depart_gps_lat', models.DecimalField(
                    blank=True, decimal_places=6, max_digits=9, null=True,
                    verbose_name='GPS départ — latitude')),
                ('depart_gps_lng', models.DecimalField(
                    blank=True, decimal_places=6, max_digits=9, null=True,
                    verbose_name='GPS départ — longitude')),
                ('note', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Note')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_pointages',
                    to='authentication.company',
                    verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pointages',
                    to='rh.dossieremploye',
                    verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Pointage',
                'verbose_name_plural': 'Pointages',
                'ordering': ['-heure_arrivee', '-date_creation'],
                'indexes': [
                    models.Index(
                        fields=['company', 'employe'],
                        name='rh_pointage_comp_employe_idx'),
                    models.Index(
                        fields=['company', 'heure_arrivee'],
                        name='rh_pointage_comp_arrivee_idx'),
                ],
            },
        ),
    ]
