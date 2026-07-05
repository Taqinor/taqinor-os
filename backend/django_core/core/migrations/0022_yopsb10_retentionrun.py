import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    """YOPSB10 — registre de rétention partagé : journal d'exécution
    RetentionRun (company nullable — balayage système transverse, comme
    BackupRun.company pour ses kinds système db_dump/restore_drill)."""

    dependencies = [
        ('authentication', '0001_initial'),
        ('core', '0021_yopsb3_backuprun_purge_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='RetentionRun',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('policy_name', models.CharField(
                    max_length=100, verbose_name='Politique',
                    help_text='Nom enregistré via register_retention_policy '
                              '(pas de FK — core ne connaît aucune app '
                              'domaine).')),
                ('dry_run', models.BooleanField(
                    default=True, verbose_name='Dry-run',
                    help_text='Vrai si la politique a tourné en mode '
                              'simulation (RETENTION_AUTO_APPLY inactif).')),
                ('count', models.IntegerField(
                    default=0, verbose_name='Compte',
                    help_text="Nombre d'éléments supprimés/anonymisés (0 en "
                              "dry-run si la politique ne fait que "
                              "compter).")),
                ('statut', models.CharField(
                    choices=[('ok', 'OK'), ('echec', 'Échec')],
                    default='ok', max_length=10, verbose_name='Statut')),
                ('erreur', models.TextField(
                    blank=True, default='', verbose_name='Erreur')),
                ('executed_at', models.DateTimeField(
                    default=django.utils.timezone.now,
                    verbose_name='Exécuté le')),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='retention_runs',
                    to='authentication.company', verbose_name='Société',
                    help_text='Nulle pour un balayage système transverse à '
                              'toutes les sociétés (la politique scope '
                              'elle-même en interne).')),
            ],
            options={
                'verbose_name': 'Exécution de rétention',
                'verbose_name_plural': 'Exécutions de rétention',
                'ordering': ['-executed_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='retentionrun',
            index=models.Index(
                fields=['policy_name', '-executed_at'],
                name='core_retentionrun_policy_idx'),
        ),
    ]
