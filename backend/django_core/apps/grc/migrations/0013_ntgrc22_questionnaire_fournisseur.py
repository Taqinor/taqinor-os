# NTGRC22 — questionnaires de conformité fournisseurs + leurs réponses.
# Deux tables NEUVES, purement additives. `conforme` est un booléen NULLABLE à
# trois états VOULUS (conforme / non conforme / pas encore évalué).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0012_ntgrc20_attestation_politique'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuestionnaireFournisseur',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('fournisseur_ref', models.CharField(
                    blank=True, default='',
                    help_text='Identifiant texte du stock.Fournisseur '
                              '(string-FK).',
                    max_length=64, verbose_name='Fournisseur')),
                ('type', models.CharField(
                    choices=[('securite', 'Sécurité'),
                             ('rgpd', 'RGPD / données personnelles'),
                             ('qualite', 'Qualité'), ('rse', 'RSE')],
                    default='rgpd', max_length=10, verbose_name='Type')),
                ('statut', models.CharField(
                    choices=[('envoye', 'Envoyé'), ('en_cours', 'En cours'),
                             ('complete', 'Complété'), ('valide', 'Validé'),
                             ('refuse', 'Refusé')],
                    default='envoye', max_length=10, verbose_name='Statut')),
                ('date_envoi', models.DateField(
                    blank=True, null=True, verbose_name="Date d'envoi")),
                ('date_echeance', models.DateField(
                    blank=True, null=True, verbose_name='Échéance')),
                ('score', models.PositiveIntegerField(
                    default=0,
                    help_text='Part des réponses CONFORMES sur le total des '
                              'questions, recalculée serveur — jamais saisie.',
                    verbose_name='Score de conformité (%)')),
                ('evaluateur', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Évaluateur')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Questionnaire fournisseur',
                'verbose_name_plural': 'Questionnaires fournisseurs',
                'ordering': ['-date_envoi', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ReponseQuestionnaire',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ordre', models.PositiveIntegerField(
                    default=0, verbose_name='Ordre')),
                ('question', models.TextField(verbose_name='Question')),
                ('obligatoire', models.BooleanField(
                    default=True, verbose_name='Obligatoire')),
                ('reponse', models.TextField(
                    blank=True, default='', verbose_name='Réponse')),
                ('conforme', models.BooleanField(
                    blank=True,
                    help_text='Vide = pas encore évalué (surtout pas « non '
                              'conforme »).',
                    null=True, verbose_name='Conforme')),
                ('commentaire', models.TextField(
                    blank=True, default='', verbose_name='Commentaire')),
                ('piece_key', models.CharField(
                    blank=True, default='',
                    help_text='Clé de stockage (MinIO/GED) de la preuve '
                              'fournie.',
                    max_length=255,
                    verbose_name='Pièce justificative')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('questionnaire', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reponses',
                    to='grc.questionnairefournisseur',
                    verbose_name='Questionnaire')),
            ],
            options={
                'verbose_name': 'Réponse de questionnaire',
                'verbose_name_plural': 'Réponses de questionnaire',
                'ordering': ['ordre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='questionnairefournisseur',
            index=models.Index(fields=['company', 'statut'],
                               name='grc_questionnaire_co_st_idx'),
        ),
        migrations.AddIndex(
            model_name='questionnairefournisseur',
            index=models.Index(fields=['company', 'fournisseur_ref'],
                               name='grc_questionnaire_co_frn_idx'),
        ),
        migrations.AddIndex(
            model_name='reponsequestionnaire',
            index=models.Index(fields=['company', 'questionnaire'],
                               name='grc_reponseq_co_quest_idx'),
        ),
    ]
