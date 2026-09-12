# NTGRC25 — registre des incidents de SÉCURITÉ (distinct des violations de
# données). Table NEUVE, purement additive. La violation éventuelle est reliée
# par un identifiant TEXTE (pas de FK) : l'incident survit à son dossier
# réglementaire et réciproquement.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0030_aud704_identite_employeur'),
        ('grc', '0015_ntgrc24_questionnaire_public'),
    ]

    operations = [
        migrations.CreateModel(
            name='IncidentSecurite',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reference', models.CharField(
                    blank=True, default='', max_length=40,
                    verbose_name='Référence')),
                ('titre', models.CharField(
                    max_length=200, verbose_name='Titre')),
                ('type', models.CharField(
                    choices=[('phishing', 'Hameçonnage'),
                             ('malware', 'Logiciel malveillant'),
                             ('acces_non_autorise', 'Accès non autorisé'),
                             ('perte_materiel', 'Perte ou vol de matériel'),
                             ('deni_service', 'Déni de service'),
                             ('autre', 'Autre')],
                    default='autre', max_length=20, verbose_name='Type')),
                ('severite', models.CharField(
                    choices=[('faible', 'Faible'), ('moyenne', 'Moyenne'),
                             ('elevee', 'Élevée'), ('critique', 'Critique')],
                    default='moyenne', max_length=10,
                    verbose_name='Sévérité')),
                ('date_detection', models.DateTimeField(
                    help_text="Moment où l'incident a été CONNU.",
                    verbose_name='Date de détection')),
                ('systemes_touches', models.JSONField(
                    blank=True, default=list,
                    help_text='Ex. ["messagerie", "erp", '
                              '"poste-comptabilite"].',
                    verbose_name='Systèmes touchés')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('impact', models.TextField(
                    blank=True, default='', verbose_name='Impact constaté')),
                ('statut', models.CharField(
                    choices=[('ouvert', 'Ouvert'),
                             ('en_cours', 'En cours de traitement'),
                             ('resolu', 'Résolu'), ('clos', 'Clos')],
                    default='ouvert', max_length=10, verbose_name='Statut')),
                ('assigne', models.CharField(
                    blank=True, default='', max_length=160,
                    verbose_name='Assigné à')),
                ('violation_donnees_ref', models.CharField(
                    blank=True, default='',
                    help_text='Identifiant texte de la grc.ViolationDonnees '
                              "créée par escalade (vide tant qu'aucune donnée "
                              "personnelle n'est concernée).",
                    max_length=64,
                    verbose_name='Violation de données liée')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Incident de sécurité',
                'verbose_name_plural': 'Registre des incidents de sécurité',
                'ordering': ['-date_detection', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='incidentsecurite',
            index=models.Index(fields=['company', 'statut'],
                               name='grc_incident_co_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='incidentsecurite',
            index=models.Index(fields=['company', 'severite'],
                               name='grc_incident_co_sever_idx'),
        ),
        migrations.AddConstraint(
            model_name='incidentsecurite',
            constraint=models.UniqueConstraint(
                fields=('company', 'reference'),
                name='grc_incidentsecurite_co_ref'),
        ),
    ]
