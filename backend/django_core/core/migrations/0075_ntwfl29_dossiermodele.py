# NTWFL29 — Modèles de dossier préconfigurés (« case templates ») :
# DossierModele (parent) + DossierModeleChecklistItem (checklist type
# ordonnée), même pattern que installations.ModeleProjet/ModeleProjetJalon
# (FG296). Purement ADDITIF : deux tables neuves, aucun modèle existant
# touché.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0074_nti18n39_i18ncoveragesnapshot'),
    ]

    operations = [
        migrations.CreateModel(
            name='DossierModele',
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
                    help_text='Même catalogue fermé que Dossier.type_dossier.',
                    max_length=32, verbose_name='Type de dossier')),
                ('nom', models.CharField(
                    help_text='Ex. « Réclamation complexe » — affiché dans '
                              'le sélecteur.',
                    max_length=120, verbose_name='Nom du modèle')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('actif', models.BooleanField(
                    default=True, verbose_name='Actif')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Modèle de dossier',
                'verbose_name_plural': 'Modèles de dossier',
                'ordering': ['nom'],
            },
        ),
        migrations.CreateModel(
            name='DossierModeleChecklistItem',
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
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('modele', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='checklist', to='core.dossiermodele',
                    verbose_name='Modèle de dossier')),
            ],
            options={
                'verbose_name': 'Étape type de modèle de dossier',
                'verbose_name_plural': 'Étapes type de modèle de dossier',
                'ordering': ['modele_id', 'ordre', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='dossiermodele',
            constraint=models.UniqueConstraint(
                fields=('company', 'nom'),
                name='core_dossiermodele_co_nom_uniq'),
        ),
    ]
