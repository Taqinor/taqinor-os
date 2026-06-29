# Generated 2026-06-28 — FG168 Heures supplémentaires & calcul majoré

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("rh", "0009_feuilletemps"),
    ]

    operations = [
        migrations.CreateModel(
            name='HeuresSupp',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Date')),
                ('heures_travaillees', models.DecimalField(
                    decimal_places=2, max_digits=6,
                    verbose_name='Heures travaillées')),
                ('heures_nuit', models.DecimalField(
                    decimal_places=2, default=0, max_digits=6,
                    verbose_name='Heures de nuit')),
                ('seuil_journalier', models.DecimalField(
                    decimal_places=2, default=8, max_digits=6,
                    verbose_name='Seuil journalier')),
                ('jour_repos_ferie', models.BooleanField(
                    default=False, verbose_name='Jour de repos / férié')),
                ('heures_normales', models.DecimalField(
                    decimal_places=2, default=0, max_digits=6,
                    verbose_name='Heures normales')),
                ('hs_25', models.DecimalField(
                    decimal_places=2, default=0, max_digits=6,
                    verbose_name='HS majorées 25 %')),
                ('hs_50', models.DecimalField(
                    decimal_places=2, default=0, max_digits=6,
                    verbose_name='HS majorées 50 %')),
                ('hs_100', models.DecimalField(
                    decimal_places=2, default=0, max_digits=6,
                    verbose_name='HS majorées 100 %')),
                ('taux_horaire', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=14, null=True,
                    verbose_name='Taux horaire (interne)')),
                ('montant_majore', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=16, null=True,
                    verbose_name='Montant majoré (interne)')),
                ('note', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Note')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_heures_supp',
                    to='authentication.company',
                    verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='heures_supp',
                    to='rh.dossieremploye',
                    verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Heures supplémentaires',
                'verbose_name_plural': 'Heures supplémentaires',
                'ordering': ['-date', '-date_creation'],
                'indexes': [
                    models.Index(
                        fields=['company', 'employe'],
                        name='rh_hsupp_comp_employe_idx'),
                    models.Index(
                        fields=['company', 'date'],
                        name='rh_hsupp_comp_date_idx'),
                ],
            },
        ),
    ]
