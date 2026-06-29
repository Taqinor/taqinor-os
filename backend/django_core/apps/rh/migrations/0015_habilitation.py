# Generated 2026-06-29 — FG173 Habilitations électriques par employé

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("rh", "0014_competence_competenceemploye"),
    ]

    operations = [
        migrations.CreateModel(
            name='Habilitation',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('type_habilitation', models.CharField(
                    choices=[
                        ('b0',
                         "B0 — Non-électricien (travaux d'ordre non "
                         "électrique BT)"),
                        ('h0', 'H0 — Non-électricien (zone HT)'),
                        ('h0v', 'H0V — Non-électricien (voisinage HT)'),
                        ('b1', 'B1 — Exécutant électricien BT'),
                        ('b1v', 'B1V — Exécutant électricien BT (voisinage)'),
                        ('b2', 'B2 — Chargé de travaux BT'),
                        ('b2v', 'B2V — Chargé de travaux BT (voisinage)'),
                        ('br', "BR — Chargé d'intervention générale BT"),
                        ('bc', 'BC — Chargé de consignation BT'),
                        ('be', "BE — Chargé d'opérations spécifiques BT"),
                        ('h1', 'H1 — Exécutant électricien HT'),
                        ('h1v', 'H1V — Exécutant électricien HT (voisinage)'),
                        ('h2', 'H2 — Chargé de travaux HT'),
                        ('h2v', 'H2V — Chargé de travaux HT (voisinage)'),
                        ('hc', 'HC — Chargé de consignation HT'),
                        ('bp',
                         'BP — Photovoltaïque (opérations sur installation '
                         'PV)'),
                        ('autre', 'Autre'),
                    ],
                    default='b1v', max_length=10,
                    verbose_name="Titre d'habilitation")),
                ('organisme', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Organisme délivrant')),
                ('date_obtention', models.DateField(
                    blank=True, null=True,
                    verbose_name="Date d'obtention")),
                ('date_validite', models.DateField(
                    blank=True, null=True,
                    verbose_name='Date de validité (échéance)')),
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
                    related_name='rh_habilitations',
                    to='authentication.company',
                    verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='habilitations',
                    to='rh.dossieremploye',
                    verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Habilitation électrique',
                'verbose_name_plural': 'Habilitations électriques',
                'ordering': ['employe', 'type_habilitation'],
            },
        ),
        migrations.AddIndex(
            model_name='habilitation',
            index=models.Index(
                fields=['company', 'employe'],
                name='rh_habil_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='habilitation',
            index=models.Index(
                fields=['company', 'date_validite'],
                name='rh_habil_comp_valid_idx'),
        ),
        migrations.AddConstraint(
            model_name='habilitation',
            constraint=models.UniqueConstraint(
                fields=('employe', 'type_habilitation'),
                name='rh_habil_emp_type_uniq'),
        ),
    ]
