"""NTDATA27 — destination d'entrepôt analytique par défaut : le MinIO interne.

``AlterField`` pur sur ``choices`` + ``default`` d'un CharField : AUCUN effet de
schéma en base (Django ne matérialise ni les choices ni le default), la
migration garde seulement le modèle et l'état de migration en phase
(``makemigrations --check`` en CI). Les extraits EXISTANTS conservent leur
destination telle quelle — seul un NOUVEL extrait créé sans destination
explicite vise désormais l'entrepôt MinIO interne (aucun credential externe).

CHAÎNE : enchaîne explicitement sur la dernière migration de ``core``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0044_ntai24_searchchunk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheduledexport',
            name='destination',
            field=models.CharField(
                choices=[('minio', 'Entrepôt MinIO (interne)'),
                         ('sftp', 'SFTP'),
                         ('s3', 'Bucket S3')],
                default='minio', max_length=20, verbose_name='Destination'),
        ),
    ]
