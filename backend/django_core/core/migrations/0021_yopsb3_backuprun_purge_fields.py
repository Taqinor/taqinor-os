from django.db import migrations, models


class Migration(migrations.Migration):
    """YOPSB3 — rétention GFS des BackupRun : soft-delete léger
    (``purge_is_deleted``/``purge_deleted_at``) posé avant tout retrait de
    l'objet MinIO correspondant. Additive, sans impact sur le manager par
    défaut (contrairement à SoftDeleteModel)."""

    dependencies = [
        ('core', '0020_yopsb1_backuprun_system_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='backuprun',
            name='purge_is_deleted',
            field=models.BooleanField(
                default=False, verbose_name='Purgé (rétention GFS)',
                help_text='YOPSB3 — vrai une fois retiré par la purge GFS '
                          '(soft-delete).'),
        ),
        migrations.AddField(
            model_name='backuprun',
            name='purge_deleted_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Purgé le'),
        ),
    ]
