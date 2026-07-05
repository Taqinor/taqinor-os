from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """YOPSB1 — étend BackupRun pour porter les dumps Postgres système
    (pg_dump vers MinIO) et les drills de restauration (YOPSB2) :
      * ``company`` devient nullable (ces deux kinds concernent toute
        l'instance, pas une société unique) ;
      * nouveaux kinds ``db_dump``/``restore_drill`` ;
      * ``object_key`` (clé objet MinIO) + ``bytes_taille`` (taille du dump).
    Additive et revertable : les kinds/company existants (export/restore,
    company obligatoire) restent inchangés en usage normal côté API société."""

    dependencies = [
        ('core', '0019_dsr_kind_maxlength'),
    ]

    operations = [
        migrations.AlterField(
            model_name='backuprun',
            name='company',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='backup_runs', to='authentication.company',
                verbose_name='Société',
                help_text="Nulle UNIQUEMENT pour les kinds système "
                          "db_dump/restore_drill (toute l'instance, pas une "
                          "société)."),
        ),
        migrations.AlterField(
            model_name='backuprun',
            name='kind',
            field=models.CharField(
                choices=[
                    ('export', 'Sauvegarde'),
                    ('restore', 'Restauration'),
                    ('db_dump', 'Dump base (pg_dump)'),
                    ('restore_drill', 'Drill de restauration'),
                ],
                default='export', max_length=14, verbose_name='Type'),
        ),
        migrations.AddField(
            model_name='backuprun',
            name='object_key',
            field=models.CharField(
                blank=True, default='', max_length=500,
                verbose_name='Clé objet MinIO',
                help_text='YOPSB1 — clé de l\'objet .dump dans le bucket '
                          'erp-backups.'),
        ),
        migrations.AddField(
            model_name='backuprun',
            name='bytes_taille',
            field=models.BigIntegerField(
                blank=True, null=True, verbose_name='Taille (octets)',
                help_text='YOPSB1 — taille du dump pg_dump produit.'),
        ),
    ]
