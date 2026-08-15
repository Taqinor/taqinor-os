"""NTMIG28 — traçabilité des déploiements menés par un partenaire.

Migration PUREMENT ADDITIVE : un ``CreateModel`` sur une table neuve, aucun
``RunPython``, aucune colonne existante touchée. Le reverse est le DROP TABLE
standard de Django.

Le FK vers ``crm.Partenaire`` est une référence par CHAÎNE (la table physique
reste ``compta_partenaire``, sortie state-only ODX13) ; les index portent un
nom EXPLICITE identique à celui déclaré dans ``Meta.indexes``.
"""
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('crm', '0076_ntmig26_certification_partenaire'),
        ('migration', '0004_ntmig22_playbookinstance'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeploiementPartenaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client_final', models.CharField(blank=True, default='', help_text='Nom libre du client déployé (jamais un FK cross-app dur).', max_length=200, verbose_name='Client final')),
                ('modules', models.JSONField(blank=True, default=list, verbose_name='Modules déployés')),
                ('date_go_live', models.DateField(blank=True, null=True, verbose_name='Date de mise en service')),
                ('statut', models.CharField(choices=[('en_cours', 'En cours'), ('reussi', 'Réussi'), ('abandonne', 'Abandonné')], default='en_cours', max_length=10, verbose_name='Statut')),
                ('note_satisfaction', models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(10)], verbose_name='Note de satisfaction (0-10)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('partenaire', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deploiements', to='crm.partenaire', verbose_name='Partenaire')),
                ('projet_migration', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deploiements_partenaire', to='migration.projetmigration', verbose_name='Projet de migration')),
            ],
            options={
                'verbose_name': 'Déploiement partenaire',
                'verbose_name_plural': 'Déploiements partenaire',
                'ordering': ['-date_go_live', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='deploiementpartenaire',
            index=models.Index(fields=['company', 'partenaire'], name='mig_deploi_soc_part_idx'),
        ),
        migrations.AddIndex(
            model_name='deploiementpartenaire',
            index=models.Index(fields=['company', 'statut'], name='mig_deploi_soc_statut_idx'),
        ),
    ]
