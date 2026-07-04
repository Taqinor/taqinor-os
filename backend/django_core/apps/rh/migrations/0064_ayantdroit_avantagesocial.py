# Generated for XRH29 — ayants droit & avantages sociaux.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0063_departement_parent'),
    ]

    operations = [
        migrations.CreateModel(
            name='AyantDroit',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('lien', models.CharField(choices=[
                    ('conjoint', 'Conjoint(e)'),
                    ('enfant', 'Enfant'),
                    ('autre', 'Autre'),
                ], max_length=20, verbose_name='Lien')),
                ('nom', models.CharField(max_length=160, verbose_name='Nom')),
                ('date_naissance', models.DateField(
                    blank=True, null=True,
                    verbose_name='Date de naissance')),
                ('couvert_amo', models.BooleanField(
                    default=False, verbose_name='Couvert AMO')),
                ('couvert_mutuelle', models.BooleanField(
                    default=False, verbose_name='Couvert mutuelle')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_ayants_droit',
                    to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ayants_droit', to='rh.dossieremploye',
                    verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Ayant droit',
                'verbose_name_plural': 'Ayants droit',
                'ordering': ['employe', 'nom'],
            },
        ),
        migrations.AddIndex(
            model_name='ayantdroit',
            index=models.Index(
                fields=['company', 'employe'],
                name='rh_ayant_droit_comp_emp_idx'),
        ),
        migrations.CreateModel(
            name='AvantageSocial',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('type', models.CharField(choices=[
                    ('mutuelle', 'Mutuelle'),
                    ('assurance_groupe', 'Assurance groupe'),
                    ('cimr', 'CIMR'),
                    ('autre', 'Autre'),
                ], max_length=20, verbose_name='Type')),
                ('organisme', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Organisme')),
                ('date_adhesion', models.DateField(
                    blank=True, null=True,
                    verbose_name="Date d'adhésion")),
                ('date_fin', models.DateField(
                    blank=True, null=True, verbose_name='Date de fin')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_avantages_sociaux',
                    to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='avantages_sociaux', to='rh.dossieremploye',
                    verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Avantage social',
                'verbose_name_plural': 'Avantages sociaux',
                'ordering': ['employe', 'type'],
            },
        ),
        migrations.AddIndex(
            model_name='avantagesocial',
            index=models.Index(
                fields=['company', 'employe'],
                name='rh_avantage_comp_emp_idx'),
        ),
    ]
