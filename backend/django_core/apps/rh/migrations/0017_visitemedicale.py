# Generated 2026-06-29 — FG177 Visite médicale du travail par employé

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rh", "0016_certification"),
    ]

    operations = [
        migrations.CreateModel(
            name='VisiteMedicale',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('date_visite', models.DateField(
                    blank=True, null=True,
                    verbose_name='Date de la visite')),
                ('prochaine_visite', models.DateField(
                    blank=True, null=True,
                    verbose_name='Prochaine visite (échéance)')),
                ('aptitude', models.CharField(
                    choices=[
                        ('apte', 'Apte'),
                        ('apte_avec_restrictions', 'Apte avec restrictions'),
                        ('inapte', 'Inapte'),
                    ],
                    default='apte', max_length=24,
                    verbose_name="Verdict d'aptitude")),
                ('medecin', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Médecin du travail')),
                ('organisme', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Organisme / service de santé au travail')),
                ('restrictions', models.TextField(
                    blank=True, default='',
                    verbose_name='Restrictions de poste')),
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
                    related_name='rh_visites_medicales',
                    to='authentication.company',
                    verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='visites_medicales',
                    to='rh.dossieremploye',
                    verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Visite médicale du travail',
                'verbose_name_plural': 'Visites médicales du travail',
                'ordering': ['employe', '-date_visite'],
            },
        ),
        migrations.AddIndex(
            model_name='visitemedicale',
            index=models.Index(
                fields=['company', 'employe'],
                name='rh_vismed_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='visitemedicale',
            index=models.Index(
                fields=['company', 'prochaine_visite'],
                name='rh_vismed_comp_proch_idx'),
        ),
    ]
