# Generated for XRH34 — eLearning léger : quiz d'évaluation + parcours de
# certification (re-certification sur expiration). Additif.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('rh', '0066_ouverture_publique'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuizFormation',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('intitule', models.CharField(
                    max_length=200, verbose_name='Intitulé')),
                ('questions', models.JSONField(
                    blank=True, default=list, verbose_name='Questions')),
                ('score_reussite', models.PositiveSmallIntegerField(
                    default=80, verbose_name='Score de réussite (%)')),
                ('validite_mois', models.PositiveIntegerField(
                    blank=True, null=True,
                    verbose_name='Validité de la certification (mois)')),
                ('habilitation_type', models.CharField(
                    blank=True, default='',
                    choices=[
                        ('b0', "B0 — Non-électricien (travaux d'ordre non "
                               'électrique BT)'),
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
                        ('bp', 'BP — Photovoltaïque (opérations sur '
                               'installation PV)'),
                        ('autre', 'Autre'),
                    ],
                    max_length=10, verbose_name="Type d'habilitation liée")),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(
                    auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_quiz_formation',
                    to='authentication.company', verbose_name='Société')),
                ('competence', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='quiz', to='rh.competence',
                    verbose_name='Compétence liée')),
            ],
            options={
                'verbose_name': 'Quiz de formation',
                'verbose_name_plural': 'Quiz de formation',
                'ordering': ['intitule'],
            },
        ),
        migrations.AddIndex(
            model_name='quizformation',
            index=models.Index(
                fields=['company', 'actif'],
                name='rh_quiz_comp_actif_idx'),
        ),
        migrations.CreateModel(
            name='TentativeQuiz',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('reponses', models.JSONField(
                    blank=True, default=list, verbose_name='Réponses')),
                ('score', models.PositiveSmallIntegerField(
                    default=0, verbose_name='Score (%)')),
                ('reussi', models.BooleanField(
                    default=False, verbose_name='Réussi')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_tentatives_quiz',
                    to='authentication.company', verbose_name='Société')),
                ('quiz', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tentatives', to='rh.quizformation',
                    verbose_name='Quiz')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tentatives_quiz', to='rh.dossieremploye',
                    verbose_name='Employé')),
                ('session', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='tentatives_quiz',
                    to='rh.sessionformation', verbose_name='Session liée')),
            ],
            options={
                'verbose_name': 'Tentative de quiz',
                'verbose_name_plural': 'Tentatives de quiz',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='tentativequiz',
            index=models.Index(
                fields=['company', 'employe'],
                name='rh_tquiz_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='tentativequiz',
            index=models.Index(
                fields=['company', 'quiz'],
                name='rh_tquiz_comp_quiz_idx'),
        ),
    ]
