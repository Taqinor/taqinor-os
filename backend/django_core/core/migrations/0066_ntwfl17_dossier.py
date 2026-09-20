# NTWFL17 — Dossier transverse (« case ») : en-tête + objets liés
# (contenttypes, jamais de FK vers une app domaine) + checklist. Purement
# ADDITIF : trois tables neuves, aucun modèle existant touché.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0065_ntgrc27_traitement_haut_risque'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('authentication', '0013_customuser_poste_ref'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Dossier',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_dossier', models.CharField(
                    choices=[
                        ('reclamation_complexe', 'Réclamation complexe'),
                        ('onboarding_grand_compte',
                         'Onboarding grand compte'),
                        ('litige', 'Litige'),
                        ('projet_transverse', 'Projet transverse'),
                        ('autre', 'Autre'),
                    ],
                    default='autre',
                    help_text='Catalogue fermé — étendu par migration, '
                              'jamais par saisie.',
                    max_length=32, verbose_name='Type de dossier')),
                ('titre', models.CharField(
                    max_length=200, verbose_name='Titre')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('statut', models.CharField(
                    choices=[
                        ('ouvert', 'Ouvert'),
                        ('en_cours', 'En cours'),
                        ('en_attente', 'En attente'),
                        ('clos', 'Clos'),
                        ('abandonne', 'Abandonné'),
                    ],
                    default='ouvert',
                    help_text='Cycle de vie PROPRE au dossier — sans rapport '
                              'avec le funnel commercial (STAGES.py).',
                    max_length=16, verbose_name='Statut')),
                ('priorite', models.CharField(
                    choices=[
                        ('basse', 'Basse'),
                        ('normale', 'Normale'),
                        ('haute', 'Haute'),
                        ('critique', 'Critique'),
                    ],
                    default='normale', max_length=16,
                    verbose_name='Priorité')),
                ('echeance', models.DateField(
                    blank=True, null=True,
                    help_text='Vide = aucune date cible surveillée.',
                    verbose_name='Échéance')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('proprietaire', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='core_dossiers_possedes',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Propriétaire')),
            ],
            options={
                'verbose_name': 'Dossier',
                'verbose_name_plural': 'Dossiers',
                'ordering': ['-id'],
            },
        ),
        migrations.CreateModel(
            name='DossierLien',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_id', models.PositiveIntegerField(
                    verbose_name='Identifiant de la cible')),
                ('libelle', models.CharField(
                    blank=True, default='',
                    help_text='Intitulé figé de la cible au moment du '
                              'rattachement.',
                    max_length=200, verbose_name='Libellé')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('content_type', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='+', to='contenttypes.contenttype',
                    verbose_name='Type de cible')),
                ('dossier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='liens', to='core.dossier',
                    verbose_name='Dossier')),
            ],
            options={
                'verbose_name': 'Objet lié au dossier',
                'verbose_name_plural': 'Objets liés au dossier',
                'ordering': ['dossier', 'id'],
            },
        ),
        migrations.CreateModel(
            name='DossierChecklistItem',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('libelle', models.CharField(
                    max_length=200, verbose_name='Libellé')),
                ('ordre', models.PositiveIntegerField(
                    default=0, verbose_name='Ordre')),
                ('fait', models.BooleanField(
                    default=False, verbose_name='Fait')),
                ('fait_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Fait le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('dossier', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='checklist', to='core.dossier',
                    verbose_name='Dossier')),
                ('fait_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='core_dossier_items_faits',
                    to=settings.AUTH_USER_MODEL, verbose_name='Fait par')),
            ],
            options={
                'verbose_name': 'Étape de checklist (dossier)',
                'verbose_name_plural': 'Étapes de checklist (dossier)',
                'ordering': ['dossier', 'ordre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='dossier',
            index=models.Index(fields=['company', 'statut'],
                               name='core_dossier_co_statut_idx'),
        ),
        migrations.AddIndex(
            model_name='dossier',
            index=models.Index(fields=['company', 'type_dossier'],
                               name='core_dossier_co_type_idx'),
        ),
        migrations.AddIndex(
            model_name='dossier',
            index=models.Index(fields=['company', 'echeance'],
                               name='core_dossier_co_ech_idx'),
        ),
        migrations.AddIndex(
            model_name='dossierlien',
            index=models.Index(fields=['content_type', 'object_id'],
                               name='core_doslien_target_idx'),
        ),
        migrations.AddConstraint(
            model_name='dossierlien',
            constraint=models.UniqueConstraint(
                fields=('dossier', 'content_type', 'object_id'),
                name='core_dossier_lien_uniq'),
        ),
        migrations.AddIndex(
            model_name='dossierchecklistitem',
            index=models.Index(fields=['dossier', 'ordre'],
                               name='core_dositem_ordre_idx'),
        ),
    ]
