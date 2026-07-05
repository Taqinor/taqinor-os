import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('dataimport', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImportMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=150)),
                ('entity', models.CharField(max_length=50)),
                ('mapping', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dataimport_mappings', to='authentication.company')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='ImportJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target', models.CharField(max_length=50)),
                ('fichier_nom', models.CharField(blank=True, max_length=255, null=True)),
                ('mode', models.CharField(default='creer', max_length=20)),
                ('statut', models.CharField(choices=[('ok', 'Terminé'), ('partiel', 'Terminé avec erreurs'), ('echec', 'Échoué (rollback)')], default='ok', max_length=10)),
                ('total_lignes', models.PositiveIntegerField(default=0)),
                ('created_count', models.PositiveIntegerField(default=0)),
                ('updated_count', models.PositiveIntegerField(default=0)),
                ('error_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dataimport_jobs', to='authentication.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dataimport_jobs', to='authentication.customuser')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ImportJobRow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ligne', models.PositiveIntegerField()),
                ('statut', models.CharField(choices=[('ok', 'Importée'), ('erreur', 'Erreur')], max_length=10)),
                ('motif', models.CharField(blank=True, max_length=255, null=True)),
                ('donnees', models.JSONField(blank=True, default=dict)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rows', to='dataimport.importjob')),
            ],
            options={
                'ordering': ['ligne'],
            },
        ),
        migrations.AddIndex(
            model_name='importjob',
            index=models.Index(fields=['company', 'target'], name='dataimport__company_5d1e2a_idx'),
        ),
        migrations.AddIndex(
            model_name='importjobrow',
            index=models.Index(fields=['job', 'statut'], name='dataimport__job_id_9b1c3a_idx'),
        ),
        migrations.AddConstraint(
            model_name='importmapping',
            constraint=models.UniqueConstraint(fields=('company', 'entity', 'nom'), name='uniq_dataimport_mapping_nom'),
        ),
    ]
