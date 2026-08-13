# NTEXT7 — étape « Attendre » : nouveau choix WAIT (règle + étape) et modèle
# AutomationScheduledStep (échéance de reprise d'une séquence suspendue).
# Purement ADDITIF : aucune table existante n'est modifiée au-delà des
# `choices` déclarés en Python.

import django.db.models.deletion
from django.db import migrations, models

CHOICES = [
    ('send_whatsapp', 'Envoyer un WhatsApp'),
    ('send_email', 'Envoyer un email'),
    ('send_sms', 'Envoyer un SMS'),
    ('create_activity', 'Créer une activité / tâche'),
    ('assign_record', 'Assigner un enregistrement'),
    ('set_field', 'Mettre à jour un champ'),
    ('create_sav_ticket', 'Créer un ticket SAV'),
    ('create_custom_record', 'Créer un enregistrement personnalisé'),
    ('for_each', "Pour chaque élément d'une liste"),
    ('wait', 'Attendre (délai avant la suite)'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('automation', '0015_ntext6_for_each'),
    ]

    operations = [
        migrations.AlterField(
            model_name='automationrule',
            name='action_type',
            field=models.CharField(choices=CHOICES, max_length=40),
        ),
        migrations.AlterField(
            model_name='automationstep',
            name='action_type',
            field=models.CharField(choices=CHOICES, max_length=40),
        ),
        migrations.CreateModel(
            name='AutomationScheduledStep',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('target_model', models.CharField(
                    blank=True, default='', max_length=120)),
                ('target_id', models.PositiveIntegerField(
                    blank=True, null=True)),
                ('next_step_index', models.PositiveIntegerField(
                    default=0,
                    help_text="Rang (0-based) de l'étape par laquelle "
                              "reprendre.")),
                ('run_at', models.DateTimeField(
                    help_text='Date/heure à partir de laquelle la séquence '
                              'reprend.')),
                ('context', models.JSONField(blank=True, default=dict)),
                ('statut', models.CharField(
                    choices=[('en_attente', 'En attente'),
                             ('reprise', 'Reprise'),
                             ('annulee', 'Annulée')],
                    default='en_attente', max_length=20)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_reprise', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='automation_scheduled_steps',
                    to='authentication.company')),
                ('rule', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scheduled_steps',
                    to='automation.automationrule', verbose_name='Règle')),
            ],
            options={
                'verbose_name': "Reprise d'automatisation planifiée",
                'verbose_name_plural': "Reprises d'automatisation planifiées",
                'ordering': ['run_at', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='automationscheduledstep',
            index=models.Index(fields=['statut', 'run_at'],
                               name='automation_sched_due_idx'),
        ),
        migrations.AddIndex(
            model_name='automationscheduledstep',
            index=models.Index(fields=['company', 'statut'],
                               name='automation_sched_co_idx'),
        ),
    ]
