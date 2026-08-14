"""NTMIG22 — checklist de déploiement instanciée depuis un playbook kb.

Migration PUREMENT ADDITIVE : un ``CreateModel`` sur une table neuve, aucun
``RunPython``, aucune colonne existante touchée. Le reverse est le DROP TABLE
standard de Django — il ne peut détruire que des lignes créées APRÈS cette
migration.

Les index portent un nom EXPLICITE (≤30 caractères), identique à celui déclaré
dans ``Meta.indexes`` : un nom haché recopié à la main diverge du nom recalculé
par Django et fait échouer le contrôle de dérive modèle↔migration.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('kb', '0024_ntmig21_playbook'),
        ('migration', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlaybookInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('playbook_titre', models.CharField(blank=True, default='', help_text="Titre figé à l'instanciation (reste lisible si l'article modèle est supprimé ou renommé).", max_length=255, verbose_name='Titre du playbook')),
                ('client_final', models.CharField(blank=True, default='', help_text='Nom libre du client déployé (jamais un FK cross-app dur).', max_length=200, verbose_name='Client final')),
                ('etapes', models.JSONField(blank=True, default=list, verbose_name='Étapes (instantané)')),
                ('avancement', models.JSONField(blank=True, default=dict, verbose_name='Avancement')),
                ('statut', models.CharField(choices=[('en_cours', 'En cours'), ('termine', 'Terminé')], default='en_cours', max_length=10, verbose_name='Statut')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('playbook_article', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='instances_playbook', to='kb.kbarticle', verbose_name='Playbook (article kb)')),
                ('projet_migration', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='playbooks', to='migration.projetmigration', verbose_name='Projet de migration')),
                ('responsable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='playbooks_migration', to=settings.AUTH_USER_MODEL, verbose_name='Responsable')),
            ],
            options={
                'verbose_name': 'Instance de playbook',
                'verbose_name_plural': 'Instances de playbook',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='playbookinstance',
            index=models.Index(fields=['company', 'statut'], name='mig_playbook_soc_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='playbookinstance',
            index=models.Index(fields=['company', 'projet_migration'], name='mig_playbook_soc_projet_idx'),
        ),
    ]
