# NTMIG — création initiale des tables du groupe Migration ERP.
#
# Migration PUREMENT ADDITIVE : trois CreateModel sur des tables neuves, aucun
# RunPython, aucune donnée déplacée ni réécrite, aucune colonne existante
# touchée. Le reverse est donc le DROP TABLE standard de Django, qui ne peut
# détruire que des lignes créées APRÈS cette migration — il n'existe aucune
# donnée préexistante qu'un retour arrière pourrait perdre.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('dataimport', '0004_importjob_ecraser_importjobrow_modifications'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjetMigration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nom', models.CharField(max_length=200)),
                ('source', models.CharField(choices=[('odoo', 'Odoo'), ('sage', 'Sage'), ('excel', 'Excel'), ('csv_generique', 'CSV générique')], default='excel', max_length=20)),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('analyse', 'Analyse'), ('chargement', 'Chargement'), ('reconciliation', 'Réconciliation'), ('termine', 'Terminé'), ('echoue', 'Échoué')], default='brouillon', max_length=20)),
                ('date_debut', models.DateTimeField(blank=True, null=True)),
                ('date_fin', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('cree_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='projets_migration_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Projet de migration',
                'verbose_name_plural': 'Projets de migration',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='LotMigration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('entite', models.CharField(help_text='Clé de cible d\'import ``dataimport.TARGETS`` (clients, products, fournisseurs…).', max_length=50)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('statut', models.CharField(choices=[('en_attente', 'En attente'), ('analyse', 'Analysé'), ('charge', 'Chargé'), ('reconcilie', 'Réconcilié'), ('echoue', 'Échoué')], default='en_attente', max_length=20)),
                ('source_lignes', models.PositiveIntegerField(default=0)),
                ('crees', models.PositiveIntegerField(default=0)),
                ('maj', models.PositiveIntegerField(default=0)),
                ('erreurs', models.PositiveIntegerField(default=0)),
                ('source_montant', models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ('derogation_reconcile', models.BooleanField(default=False)),
                ('derogation_motif', models.TextField(blank=True, default='')),
                ('derogation_at', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('derogation_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lots_migration_deroges', to=settings.AUTH_USER_MODEL)),
                ('import_job', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lots_migration', to='dataimport.importjob')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lots', to='migration.projetmigration')),
            ],
            options={
                'verbose_name': 'Lot de migration',
                'verbose_name_plural': 'Lots de migration',
                'ordering': ['projet', 'ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RapportReconciliation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nb_source', models.PositiveIntegerField(default=0)),
                ('nb_cible_crees', models.PositiveIntegerField(default=0)),
                ('nb_cible_existants', models.PositiveIntegerField(default=0)),
                ('nb_erreurs', models.PositiveIntegerField(default=0)),
                ('total_financier_source', models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ('total_financier_cible', models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ('ecart_financier', models.DecimalField(blank=True, decimal_places=2, max_digits=16, null=True)),
                ('ecarts', models.JSONField(blank=True, default=list)),
                ('conforme', models.BooleanField(default=False)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('lot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rapports', to='migration.lotmigration')),
            ],
            options={
                'verbose_name': 'Rapport de réconciliation',
                'verbose_name_plural': 'Rapports de réconciliation',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='projetmigration',
            index=models.Index(fields=['company', 'statut'], name='migration_p_company_7df09e_idx'),
        ),
        migrations.AddIndex(
            model_name='lotmigration',
            index=models.Index(fields=['company', 'projet'], name='migration_l_company_a22050_idx'),
        ),
        migrations.AddIndex(
            model_name='rapportreconciliation',
            index=models.Index(fields=['company', 'lot'], name='migration_r_company_c62619_idx'),
        ),
    ]
