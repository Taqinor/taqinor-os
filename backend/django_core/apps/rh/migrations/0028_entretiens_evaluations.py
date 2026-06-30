# Generated 2026-06-30 — FG190 Entretiens & évaluations annuelles
#
# Entièrement additive : ``CreateModel`` (``CampagneEvaluation``,
# ``EvaluationEmploye``, ``ObjectifIndividuel``) + contrainte d'unicité +
# index nommés — réversible. La campagne porte un intitulé, une année, une
# période, des dates, un statut (ouverte → clôturée) et une description. Chaque
# entretien (EvaluationEmploye) rattache un employé évalué + un évaluateur
# (DossierEmploye, même société) à une campagne, avec une note globale (1–5),
# une synthèse et un statut (planifié → réalisé → validé) ; le couple
# (campagne, employe) est unique. Les objectifs individuels (libellé,
# pondération, cible, atteinte, note) vivent dans ObjectifIndividuel. Société
# posée côté serveur. C'est l'appréciation RH — DISTINCTE des objectifs
# commerciaux de vente (FG39). RUNTIME-SAFETY (leçon FG136) : codes bornés
# ``statut`` ≤ 20 ; chaînes plafonnées ; descriptions/synthèses en TextField ;
# notes/pondérations en DecimalField borné ; index nommés explicitement
# (≤ 30 chars).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0027_recrutement_ats'),
    ]

    operations = [
        migrations.CreateModel(
            name='CampagneEvaluation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intitule', models.CharField(max_length=255, verbose_name='Intitulé')),
                ('annee', models.PositiveIntegerField(verbose_name='Année')),
                ('periode', models.CharField(blank=True, default='', max_length=60, verbose_name='Période')),
                ('date_debut', models.DateField(blank=True, null=True, verbose_name='Date de début')),
                ('date_fin', models.DateField(blank=True, null=True, verbose_name='Date de fin')),
                ('statut', models.CharField(choices=[('ouverte', 'Ouverte'), ('cloturee', 'Clôturée')], default='ouverte', max_length=20, verbose_name='Statut')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_campagnes_evaluation', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Campagne d'appréciation",
                'verbose_name_plural': "Campagnes d'appréciation",
                'ordering': ['-annee', '-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='EvaluationEmploye',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_entretien', models.DateField(blank=True, null=True, verbose_name="Date de l'entretien")),
                ('note_globale', models.DecimalField(blank=True, decimal_places=1, max_digits=3, null=True, verbose_name='Note globale')),
                ('synthese', models.TextField(blank=True, default='', verbose_name='Synthèse')),
                ('statut', models.CharField(choices=[('planifie', 'Planifié'), ('realise', 'Réalisé'), ('valide', 'Validé')], default='planifie', max_length=20, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('campagne', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluations', to='rh.campagneevaluation', verbose_name='Campagne')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_evaluations_employe', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluations_recues', to='rh.dossieremploye', verbose_name='Employé')),
                ('evaluateur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evaluations_menees', to='rh.dossieremploye', verbose_name='Évaluateur')),
            ],
            options={
                'verbose_name': "Entretien d'évaluation",
                'verbose_name_plural': "Entretiens d'évaluation",
                'ordering': ['-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='ObjectifIndividuel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=255, verbose_name='Libellé')),
                ('ponderation', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='Pondération (%)')),
                ('cible', models.CharField(blank=True, default='', max_length=255, verbose_name='Cible')),
                ('atteinte', models.CharField(blank=True, default='', max_length=255, verbose_name='Atteinte')),
                ('note', models.DecimalField(blank=True, decimal_places=1, max_digits=3, null=True, verbose_name='Note')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_objectifs_individuels', to='authentication.company', verbose_name='Société')),
                ('evaluation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='objectifs', to='rh.evaluationemploye', verbose_name='Évaluation')),
            ],
            options={
                'verbose_name': 'Objectif individuel',
                'verbose_name_plural': 'Objectifs individuels',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='campagneevaluation',
            index=models.Index(fields=['company', 'annee'], name='rh_camp_comp_annee_idx'),
        ),
        migrations.AddIndex(
            model_name='campagneevaluation',
            index=models.Index(fields=['company', 'statut'], name='rh_camp_comp_stat_idx'),
        ),
        migrations.AddConstraint(
            model_name='evaluationemploye',
            constraint=models.UniqueConstraint(fields=('campagne', 'employe'), name='rh_eval_camp_emp_uniq'),
        ),
        migrations.AddIndex(
            model_name='evaluationemploye',
            index=models.Index(fields=['company', 'campagne'], name='rh_eval_comp_camp_idx'),
        ),
        migrations.AddIndex(
            model_name='evaluationemploye',
            index=models.Index(fields=['company', 'statut'], name='rh_eval_comp_stat_idx'),
        ),
        migrations.AddIndex(
            model_name='objectifindividuel',
            index=models.Index(fields=['company', 'evaluation'], name='rh_obj_comp_eval_idx'),
        ),
    ]
