# Generated for PROJ35 -- Templates de projet par type d'installation.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('gestion_projet', '0019_commentaireprojet'),
    ]

    operations = [
        migrations.CreateModel(
            name='ModeleProjet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200, verbose_name='Nom du modèle')),
                ('type_installation', models.CharField(choices=[('residentiel', 'Résidentiel'), ('industriel', 'Industriel / Commercial'), ('agricole', 'Agricole (pompage)'), ('autre', 'Autre')], default='residentiel', max_length=12, verbose_name="Type d'installation")),
                ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_modeles', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Modèle de projet',
                'verbose_name_plural': 'Modèles de projet',
                'ordering': ['nom', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ModeleTache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type_phase', models.CharField(choices=[('etude', 'Étude'), ('appro', 'Approvisionnement'), ('pose', 'Pose'), ('mes', 'Mise en service'), ('reception', 'Réception')], default='etude', max_length=12, verbose_name='Type de phase')),
                ('code_wbs', models.CharField(blank=True, default='', max_length=50, verbose_name='Code WBS')),
                ('libelle', models.CharField(max_length=200, verbose_name='Libellé')),
                ('ordre', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                ('charge_estimee', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='Charge estimée (j-h)')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_modele_taches', to='authentication.company', verbose_name='Société')),
                ('modele', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='taches', to='gestion_projet.modeleprojet', verbose_name='Modèle')),
            ],
            options={
                'verbose_name': 'Tâche-type de modèle',
                'verbose_name_plural': 'Tâches-types de modèle',
                'ordering': ['modele', 'ordre', 'id'],
                'indexes': [models.Index(fields=['modele', 'ordre'], name='gp_modtache_mod_idx')],
            },
        ),
        migrations.AddConstraint(
            model_name='modeleprojet',
            constraint=models.UniqueConstraint(fields=('company', 'nom'), name='gp_modele_company_nom_uniq'),
        ),
    ]
