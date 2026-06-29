# Generated 2026-06-29 — FG172 Matrice de compétences (catalogue + niveau/employé)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("rh", "0013_incidentpresence"),
    ]

    operations = [
        migrations.CreateModel(
            name='Competence',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=40, verbose_name='Code')),
                ('libelle', models.CharField(
                    max_length=120, verbose_name='Libellé')),
                ('domaine', models.CharField(
                    choices=[
                        ('pose_structure', 'Pose structure'),
                        ('raccordement_dc', 'Raccordement DC'),
                        ('raccordement_ac', 'Raccordement AC'),
                        ('mes_onduleur', 'MES onduleur'),
                        ('pompage', 'Pompage'),
                        ('soudure', 'Soudure'),
                        ('autre', 'Autre'),
                    ],
                    default='autre', max_length=20, verbose_name='Domaine')),
                ('description', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Description')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_competences',
                    to='authentication.company',
                    verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Compétence',
                'verbose_name_plural': 'Compétences',
                'ordering': ['domaine', 'libelle'],
            },
        ),
        migrations.CreateModel(
            name='CompetenceEmploye',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('niveau', models.PositiveSmallIntegerField(
                    choices=[
                        (0, 'Non acquis'),
                        (1, 'Débutant'),
                        (2, 'Intermédiaire'),
                        (3, 'Confirmé'),
                        (4, 'Expert'),
                    ],
                    default=0, verbose_name='Niveau')),
                ('note', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Note')),
                ('evalue_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Évalué le')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_competences_employe',
                    to='authentication.company',
                    verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='competences',
                    to='rh.dossieremploye',
                    verbose_name='Employé')),
                ('competence', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='niveaux_employes',
                    to='rh.competence',
                    verbose_name='Compétence')),
                ('evalue_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='rh_competences_evaluees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Évalué par')),
            ],
            options={
                'verbose_name': 'Niveau de compétence',
                'verbose_name_plural': 'Niveaux de compétence',
                'ordering': ['competence', '-niveau'],
            },
        ),
        migrations.AddIndex(
            model_name='competence',
            index=models.Index(
                fields=['company', 'domaine'],
                name='rh_competence_dom_idx'),
        ),
        migrations.AddConstraint(
            model_name='competence',
            constraint=models.UniqueConstraint(
                fields=('company', 'code'),
                name='rh_competence_uniq_code'),
        ),
        migrations.AddIndex(
            model_name='competenceemploye',
            index=models.Index(
                fields=['company', 'competence', 'niveau'],
                name='rh_comp_emp_lvl_idx'),
        ),
        migrations.AddIndex(
            model_name='competenceemploye',
            index=models.Index(
                fields=['company', 'employe'],
                name='rh_comp_emp_idx'),
        ),
        migrations.AddConstraint(
            model_name='competenceemploye',
            constraint=models.UniqueConstraint(
                fields=('employe', 'competence'),
                name='rh_competence_emp_uniq'),
        ),
    ]
