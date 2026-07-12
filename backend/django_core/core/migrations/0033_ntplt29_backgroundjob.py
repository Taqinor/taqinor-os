import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """NTPLT29 — jobs de fond avec progression : modèle ``BackgroundJob``
    (company, user, kind, statut, progress_pct, result_file_key MinIO,
    message_erreur). Socle des exports lourds asynchrones (NTPLT30) et du
    commit dataimport long."""

    dependencies = [
        ('authentication', '0001_initial'),
        ('core', '0032_ntplt55_maintenancemode'),
    ]

    operations = [
        migrations.CreateModel(
            name='BackgroundJob',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('kind', models.CharField(max_length=64, verbose_name='Type')),
                ('statut', models.CharField(
                    choices=[
                        ('queued', 'En file'), ('running', 'En cours'),
                        ('done', 'Terminé'), ('failed', 'Échoué'),
                    ],
                    default='queued', max_length=16, verbose_name='Statut')),
                ('progress_pct', models.PositiveSmallIntegerField(
                    default=0, verbose_name='Progression (%)')),
                ('result_file_key', models.CharField(
                    blank=True, default='', max_length=512,
                    verbose_name='Clé fichier résultat')),
                ('message_erreur', models.TextField(
                    blank=True, default='', verbose_name='Message d’erreur')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='core_backgroundjob_set',
                    to='authentication.company', verbose_name='Société')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='background_jobs',
                    to='authentication.customuser',
                    verbose_name='Utilisateur')),
            ],
            options={
                'verbose_name': 'Job de fond',
                'verbose_name_plural': 'Jobs de fond',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='backgroundjob',
            index=models.Index(
                fields=['company', 'user', '-created_at'],
                name='core_bgjob_co_user_idx'),
        ),
    ]
