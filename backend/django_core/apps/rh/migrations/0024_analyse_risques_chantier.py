# Generated 2026-06-30 — FG184 Analyse de risques chantier (plan de prévention)
#
# Entièrement additive : ``CreateModel`` (``AnalyseRisquesChantier`` +
# ``LigneRisqueChantier``) + index nommés — réversible. L'analyse de risques
# matérialise le PLAN DE PRÉVENTION établi AVANT le démarrage d'un chantier
# (distinct de la check-list par intervention F18 et de la causerie du jour
# FG183) : dangers identifiés EN AMONT + mesures de prévention. Société posée
# côté serveur ; chantier référencé par chaîne (pas de FK inter-app).
# RUNTIME-SAFETY (leçon FG136) : ``statut`` / ``gravite`` / ``probabilite`` /
# ``niveau`` plafonnés ≤ 20, ``danger`` / ``lieu`` / ``chantier_id`` plafonnés,
# ``description`` / ``notes`` / ``mesure_prevention`` en TextField ; index
# nommés explicitement (≤ 30 chars) pour éviter la divergence d'auto-nommage.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0023_causerie_securite'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnalyseRisquesChantier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chantier_id', models.CharField(blank=True, default='', max_length=64, verbose_name='Chantier (référence)')),
                ('date_analyse', models.DateField(verbose_name="Date de l'analyse")),
                ('lieu', models.CharField(blank=True, default='', max_length=255, verbose_name='Lieu')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('valide', 'Validé')], default='brouillon', max_length=20, verbose_name='Statut')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Notes')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('redacteur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rh_analyses_risques_redigees', to='rh.dossieremploye', verbose_name='Rédacteur')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_analyses_risques_chantier', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Analyse de risques chantier',
                'verbose_name_plural': 'Analyses de risques chantier',
                'ordering': ['-date_analyse', '-date_creation'],
            },
        ),
        migrations.CreateModel(
            name='LigneRisqueChantier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('danger', models.CharField(max_length=255, verbose_name='Danger')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('gravite', models.CharField(choices=[('faible', 'Faible'), ('moyenne', 'Moyenne'), ('elevee', 'Élevée')], default='moyenne', max_length=20, verbose_name='Gravité')),
                ('probabilite', models.CharField(choices=[('faible', 'Faible'), ('moyenne', 'Moyenne'), ('elevee', 'Élevée')], default='moyenne', max_length=20, verbose_name='Probabilité')),
                ('niveau', models.CharField(choices=[('faible', 'Faible'), ('moyen', 'Moyen'), ('eleve', 'Élevé'), ('critique', 'Critique')], default='moyen', max_length=20, verbose_name='Niveau de risque')),
                ('mesure_prevention', models.TextField(blank=True, default='', verbose_name='Mesure de prévention')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_lignes_risque_chantier', to='authentication.company', verbose_name='Société')),
                ('analyse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='risques', to='rh.analyserisqueschantier', verbose_name='Analyse')),
            ],
            options={
                'verbose_name': 'Risque chantier',
                'verbose_name_plural': 'Risques chantier',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='analyserisqueschantier',
            index=models.Index(fields=['company', 'date_analyse'], name='rh_arc_comp_date_idx'),
        ),
        migrations.AddIndex(
            model_name='analyserisqueschantier',
            index=models.Index(fields=['company', 'statut'], name='rh_arc_comp_stat_idx'),
        ),
        migrations.AddIndex(
            model_name='lignerisquechantier',
            index=models.Index(fields=['company', 'analyse'], name='rh_lrc_comp_analyse_idx'),
        ),
    ]
