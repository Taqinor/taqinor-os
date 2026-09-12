# NTGRC27 — analyse d'impact relative à la protection des données (AIPD).
# Table NEUVE, purement additive. Le traitement analysé est désigné par un
# identifiant TEXTE (`core` reste la couche FONDATION : aucune FK de `grc`
# vers ses modèles), et l'analyse survit donc à la ligne de registre.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('core', '0059_ntgrc27_traitement_haut_risque'),
        ('grc', '0016_ntgrc25_incident_securite'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnalyseImpactDPIA',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('traitement_ref', models.CharField(
                    help_text='Identifiant texte du core.RegistreTraitement '
                              '(string-FK).',
                    max_length=64, verbose_name='Traitement')),
                ('necessite_dpia', models.BooleanField(
                    default=True,
                    help_text='Décision ASSUMÉE : « non » doit être justifié '
                              "dans l'avis du DPO.",
                    verbose_name='AIPD nécessaire')),
                ('critere_declencheur', models.JSONField(
                    blank=True, default=list,
                    help_text='Ex. ["donnees_sensibles", "profilage", '
                              '"surveillance", "grande_echelle"].',
                    verbose_name='Critères déclencheurs')),
                ('risques_identifies', models.JSONField(
                    blank=True, default=list,
                    help_text='Liste de {risque, gravite, vraisemblance} ou '
                              'de libellés.',
                    verbose_name='Risques identifiés')),
                ('mesures_attenuation', models.TextField(
                    blank=True, default='',
                    verbose_name="Mesures d'atténuation")),
                ('risque_residuel', models.CharField(
                    choices=[('acceptable', 'Acceptable'),
                             ('eleve', 'Élevé')],
                    default='acceptable', max_length=12,
                    verbose_name='Risque résiduel')),
                ('avis_dpo', models.TextField(
                    blank=True, default='', verbose_name='Avis du DPO')),
                ('statut', models.CharField(
                    choices=[('brouillon', 'Brouillon'),
                             ('validee', 'Validée'),
                             ('a_reviser', 'À réviser')],
                    default='brouillon', max_length=10,
                    verbose_name='Statut')),
                ('date_validation', models.DateTimeField(
                    blank=True,
                    help_text='Posée CÔTÉ SERVEUR à la validation.',
                    null=True, verbose_name='Date de validation')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': "Analyse d'impact (AIPD)",
                'verbose_name_plural': "Analyses d'impact (AIPD)",
                'ordering': ['traitement_ref', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='analyseimpactdpia',
            index=models.Index(fields=['company', 'statut'],
                               name='grc_dpia_co_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='analyseimpactdpia',
            index=models.Index(fields=['company', 'traitement_ref'],
                               name='grc_dpia_co_trait_idx'),
        ),
    ]
