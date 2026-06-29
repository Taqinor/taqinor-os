# Generated 2026-06-29 — FG174 Certifications spécifiques par employé

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0015_habilitation"),
    ]

    operations = [
        migrations.CreateModel(
            name='Certification',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('type_certification', models.CharField(
                    choices=[
                        ('travail_hauteur', 'Travail en hauteur'),
                        ('harnais', 'Port du harnais / EPI antichute'),
                        ('caces_nacelle', 'CACES / nacelle (PEMP)'),
                        ('secourisme_sst', 'Secourisme du travail (SST)'),
                        ('conduite', 'Conduite (permis / engins)'),
                        ('autre', 'Autre'),
                    ],
                    default='travail_hauteur', max_length=20,
                    verbose_name='Type de certification')),
                ('organisme', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Organisme délivrant')),
                ('date_obtention', models.DateField(
                    blank=True, null=True,
                    verbose_name="Date d'obtention")),
                ('date_validite', models.DateField(
                    blank=True, null=True,
                    verbose_name='Date de validité (expiration)')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('note', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Note')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_certifications',
                    to='authentication.company',
                    verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='certifications',
                    to='rh.dossieremploye',
                    verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Certification spécifique',
                'verbose_name_plural': 'Certifications spécifiques',
                'ordering': ['employe', 'type_certification'],
            },
        ),
        migrations.AddIndex(
            model_name='certification',
            index=models.Index(
                fields=['company', 'employe'],
                name='rh_cert_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='certification',
            index=models.Index(
                fields=['company', 'date_validite'],
                name='rh_cert_comp_valid_idx'),
        ),
        migrations.AddConstraint(
            model_name='certification',
            constraint=models.UniqueConstraint(
                fields=('employe', 'type_certification'),
                name='rh_cert_emp_type_uniq'),
        ),
    ]
