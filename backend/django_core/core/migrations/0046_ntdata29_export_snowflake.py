"""NTDATA29 — la destination ``snowflake`` entre au catalogue (DÉSARMÉE).

``AlterField`` pur sur ``choices`` d'un CharField : AUCUN effet de schéma en
base — la migration garde seulement le modèle et l'état de migration en phase
(``makemigrations --check`` en CI). Le connecteur reste no-op tant que les
variables ``SNOWFLAKE_*`` ne sont pas provisionnées par le fondateur.

CHAÎNE : enchaîne explicitement sur la migration NTDATA27.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_ntdata27_export_minio'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheduledexport',
            name='destination',
            field=models.CharField(
                choices=[('minio', 'Entrepôt MinIO (interne)'),
                         ('sftp', 'SFTP'),
                         ('s3', 'Bucket S3'),
                         ('snowflake', 'Snowflake (entrepôt externe)')],
                default='minio', max_length=20, verbose_name='Destination'),
        ),
    ]
