# FG366 — Moteur de workflow multi-étapes (BPM) + SLA / escalades.
#
# Composant d'architecture GÉNÉRIQUE et de FONDATION. Ajoute les quatre modèles
# du moteur BPM :
#   - WorkflowDefinition / WorkflowStepDefinition  (le template)
#   - WorkflowInstance / WorkflowStepInstance       (l'exécution)
# La cible d'une instance est désignée via ``contenttypes`` (fondation Django)
# — content_type + object_id + GenericForeignKey — donc ``core`` n'importe
# aucune app métier (contrat import-linter ``core-foundation-is-a-base-layer``).
# Migration purement ADDITIVE et réversible.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0001_anomalyflag'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkflowDefinition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(help_text='Identifiant stable par société, ex. « validation_devis ».', max_length=64, verbose_name='Code')),
                ('nom', models.CharField(max_length=120, verbose_name='Nom')),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='core_workflow_definitions', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Définition de workflow',
                'verbose_name_plural': 'Définitions de workflow',
                'ordering': ['nom', 'id'],
            },
        ),
        migrations.CreateModel(
            name='WorkflowStepDefinition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ordre', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('nom', models.CharField(max_length=120, verbose_name='Nom')),
                ('type_approbation', models.CharField(choices=[('manuelle', 'Manuelle'), ('auto', 'Automatique'), ('role', 'Par rôle')], default='manuelle', max_length=16, verbose_name="Type d'approbation")),
                ('sla_heures', models.PositiveIntegerField(blank=True, help_text='Délai cible avant escalade ; vide = pas de minuterie SLA.', null=True, verbose_name='SLA (heures)')),
                ('role_requis', models.CharField(blank=True, default='', help_text='Libellé de rôle attendu pour franchir (générique, sans FK).', max_length=80, verbose_name='Rôle requis')),
                ('escalade_vers', models.CharField(blank=True, default='', help_text='Destinataire/rôle visé si le SLA est dépassé (générique).', max_length=120, verbose_name='Escalade vers')),
                ('definition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='core.workflowdefinition', verbose_name='Définition')),
            ],
            options={
                'verbose_name': 'Étape de workflow (modèle)',
                'verbose_name_plural': 'Étapes de workflow (modèle)',
                'ordering': ['definition', 'ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='WorkflowInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_id', models.PositiveIntegerField(verbose_name='Identifiant de la cible')),
                ('statut', models.CharField(choices=[('en_cours', 'En cours'), ('termine', 'Terminé'), ('annule', 'Annulé')], default='en_cours', max_length=16, verbose_name='Statut')),
                ('etape_courante', models.PositiveIntegerField(default=1, help_text="Position (1-based) de l'étape active.", verbose_name='Étape courante')),
                ('started_le', models.DateTimeField(blank=True, null=True, verbose_name='Démarré le')),
                ('ended_le', models.DateTimeField(blank=True, null=True, verbose_name='Terminé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='core_workflow_instances', to='authentication.company', verbose_name='Société')),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='contenttypes.contenttype', verbose_name='Type de cible')),
                ('definition', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='instances', to='core.workflowdefinition', verbose_name='Définition')),
            ],
            options={
                'verbose_name': 'Instance de workflow',
                'verbose_name_plural': 'Instances de workflow',
                'ordering': ['-id'],
            },
        ),
        migrations.CreateModel(
            name='WorkflowStepInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ordre', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('statut', models.CharField(choices=[('en_attente', 'En attente'), ('approuve', 'Approuvé'), ('rejete', 'Rejeté'), ('escalade', 'Escaladé')], default='en_attente', max_length=16, verbose_name='Statut')),
                ('sla_echeance', models.DateTimeField(blank=True, help_text="started + sla_heures ; vide si l'étape n'a pas de SLA.", null=True, verbose_name='Échéance SLA')),
                ('decided_le', models.DateTimeField(blank=True, null=True, verbose_name='Décidé le')),
                ('commentaire', models.TextField(blank=True, default='', verbose_name='Commentaire')),
                ('assignee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='core_workflow_steps', to=settings.AUTH_USER_MODEL, verbose_name='Assigné')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='core_workflow_step_instances', to='authentication.company', verbose_name='Société')),
                ('instance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='step_instances', to='core.workflowinstance', verbose_name='Instance')),
                ('step_def', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='step_instances', to='core.workflowstepdefinition', verbose_name="Définition d'étape")),
            ],
            options={
                'verbose_name': 'Étape de workflow (instance)',
                'verbose_name_plural': 'Étapes de workflow (instance)',
                'ordering': ['instance', 'ordre', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='workflowdefinition',
            constraint=models.UniqueConstraint(fields=('company', 'code'), name='core_wf_def_company_code_uniq'),
        ),
        migrations.AddIndex(
            model_name='workflowdefinition',
            index=models.Index(fields=['company', 'actif'], name='core_wf_def_co_actif_idx'),
        ),
        migrations.AddConstraint(
            model_name='workflowstepdefinition',
            constraint=models.UniqueConstraint(fields=('definition', 'ordre'), name='core_wf_step_def_ordre_uniq'),
        ),
        migrations.AddIndex(
            model_name='workflowstepdefinition',
            index=models.Index(fields=['definition', 'ordre'], name='core_wf_stepdef_ord_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowinstance',
            index=models.Index(fields=['company', 'statut'], name='core_wf_inst_co_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowinstance',
            index=models.Index(fields=['content_type', 'object_id'], name='core_wf_inst_target_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowstepinstance',
            index=models.Index(fields=['company', 'statut'], name='core_wf_si_co_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowstepinstance',
            index=models.Index(fields=['instance', 'ordre'], name='core_wf_si_inst_ord_idx'),
        ),
        migrations.AddIndex(
            model_name='workflowstepinstance',
            index=models.Index(fields=['statut', 'sla_echeance'], name='core_wf_si_sla_idx'),
        ),
    ]
